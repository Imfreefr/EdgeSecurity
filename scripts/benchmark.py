#!/usr/bin/env python3
"""
EdgeSecurity Multi-Camera Benchmark
Tests local inference pipeline with multiple concurrent video sources.

Usage:
    python scripts/benchmark.py --cameras 4 --duration 30 --source synthetic
    python scripts/benchmark.py --cameras 8 --duration 60 --source rtsp --urls "rtsp://..." "rtsp://..."
"""

import argparse
import asyncio
import csv
import json
import os
import sys
import time
import platform
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from queue import Queue, Empty, Full

import cv2
import numpy as np

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

try:
    from services.detector import SafetyDetector
    from services.risk_engine import assess_risk
    DETECTOR_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Detector not available: {e}")
    DETECTOR_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import GPUtil
    GPUTIL_AVAILABLE = True
except ImportError:
    GPUTIL_AVAILABLE = False


@dataclass
class CameraStats:
    camera_id: int
    frames_received: int = 0
    frames_processed: int = 0
    frames_dropped: int = 0
    inference_times: List[float] = field(default_factory=list)
    errors: int = 0
    last_fps: float = 0.0


@dataclass
class SystemMetrics:
    timestamp: float
    cpu_percent: float
    ram_used_mb: float
    ram_percent: float
    gpu_percent: float = 0.0
    vram_used_mb: float = 0.0
    vram_percent: float = 0.0


@dataclass
class BenchmarkConfig:
    num_cameras: int
    duration_seconds: int
    source_type: str  # synthetic, rtsp, webcam, video
    source_urls: List[str]
    model_path: str
    confidence: float
    iou: float
    inference_fps: int  # Target inference FPS per camera
    resolution: tuple = (640, 480)
    output_dir: str = "benchmark_results"
    queue_size: int = 2  # Max frames queued per camera (backpressure)


class VideoSource:
    """Base class for video sources"""
    
    def __init__(self, camera_id: int, config: BenchmarkConfig):
        self.camera_id = camera_id
        self.config = config
        self.cap = None
        self.running = False
        self.frame_queue: Queue = Queue(maxsize=config.queue_size)
        self.stats = CameraStats(camera_id)
        self._thread = None
    
    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self.cap:
            self.cap.release()
    
    def get_frame(self, timeout=0.1) -> Optional[np.ndarray]:
        try:
            return self.frame_queue.get(timeout=timeout)
        except Empty:
            return None
    
    def _capture_loop(self):
        raise NotImplementedError


class SyntheticSource(VideoSource):
    """Generates synthetic frames with moving objects for testing"""
    
    def __init__(self, camera_id: int, config: BenchmarkConfig):
        super().__init__(camera_id, config)
        self.frame_count = 0
        self.person_pos = [100, 100]
        self.machine_pos = [400, 300]
        self.person_vel = [2, 1]
        self.machine_vel = [-1, 2]
    
    def _capture_loop(self):
        width, height = self.config.resolution
        target_fps = 30
        frame_time = 1.0 / target_fps
        
        while self.running:
            start = time.time()
            
            # Create synthetic frame
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Draw background pattern
            frame[:, :] = (30, 30, 40)
            
            # Update positions
            self.person_pos[0] += self.person_vel[0]
            self.person_pos[1] += self.person_vel[1]
            self.machine_pos[0] += self.machine_vel[0]
            self.machine_pos[1] += self.machine_vel[1]
            
            # Bounce off walls
            for pos, vel in [(self.person_pos, self.person_vel), (self.machine_pos, self.machine_vel)]:
                if pos[0] <= 50 or pos[0] >= width - 50:
                    vel[0] *= -1
                if pos[1] <= 50 or pos[1] >= height - 50:
                    vel[1] *= -1
            
            # Draw person (green box)
            px, py = self.person_pos
            cv2.rectangle(frame, (px-25, py-50), (px+25, py+50), (0, 255, 0), 2)
            cv2.putText(frame, "PERSON", (px-25, py-55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Draw machine (orange box)
            mx, my = self.machine_pos
            cv2.rectangle(frame, (mx-40, my-30), (mx+40, my+30), (0, 165, 255), 2)
            cv2.putText(frame, "FORKLIFT", (mx-40, my-35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
            
            # Frame counter
            cv2.putText(frame, f"Cam {self.camera_id} Frame {self.frame_count}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
            
            self.frame_count += 1
            self.stats.frames_received += 1
            
            # Try to queue frame (backpressure: drop if full)
            try:
                self.frame_queue.put_nowait(frame.copy())
            except Full:
                self.stats.frames_dropped += 1
            
            # Maintain target FPS
            elapsed = time.time() - start
            sleep_time = max(0, frame_time - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)


class RTSPSource(VideoSource):
    """RTSP/IP camera source"""
    
    def __init__(self, camera_id: int, config: BenchmarkConfig, url: str):
        super().__init__(camera_id, config)
        self.url = url
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2.0
    
    def _capture_loop(self):
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                self._connect()
                if self.cap is None:
                    time.sleep(self.reconnect_delay)
                    continue
            
            ok, frame = self.cap.read()
            if not ok:
                self.cap.release()
                self.cap = None
                self.reconnect_attempts += 1
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    print(f"Camera {self.camera_id}: Max reconnect attempts reached")
                    break
                time.sleep(self.reconnect_delay)
                continue
            
            self.reconnect_attempts = 0
            self.stats.frames_received += 1
            
            try:
                self.frame_queue.put_nowait(frame)
            except Full:
                self.stats.frames_dropped += 1
    
    def _connect(self):
        print(f"Camera {self.camera_id}: Connecting to {self.url}")
        self.cap = cv2.VideoCapture(self.url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency


class WebcamSource(VideoSource):
    """Local webcam source"""
    
    def __init__(self, camera_id: int, config: BenchmarkConfig, device_id: int = 0):
        super().__init__(camera_id, config)
        self.device_id = device_id
    
    def _capture_loop(self):
        self.cap = cv2.VideoCapture(self.device_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.resolution[1])
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if not self.cap.isOpened():
            print(f"Camera {self.camera_id}: Failed to open webcam {self.device_id}")
            self.running = False
            return
        
        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                break
            
            self.stats.frames_received += 1
            try:
                self.frame_queue.put_nowait(frame)
            except Full:
                self.stats.frames_dropped += 1


class VideoFileSource(VideoSource):
    """Video file source (loops)"""
    
    def __init__(self, camera_id: int, config: BenchmarkConfig, filepath: str):
        super().__init__(camera_id, config)
        self.filepath = filepath
    
    def _capture_loop(self):
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.filepath)
                if not self.cap.isOpened():
                    print(f"Camera {self.camera_id}: Failed to open {self.filepath}")
                    break
            
            ok, frame = self.cap.read()
            if not ok:
                # Loop video
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            
            # Resize to target resolution
            frame = cv2.resize(frame, self.config.resolution)
            
            self.stats.frames_received += 1
            try:
                self.frame_queue.put_nowait(frame)
            except Full:
                self.stats.frames_dropped += 1


class InferenceWorker:
    """Runs YOLO inference on frames from multiple cameras"""
    
    def __init__(self, config: BenchmarkConfig, sources: List[VideoSource]):
        self.config = config
        self.sources = sources
        self.running = False
        self.detector = None
        self.system_metrics: List[SystemMetrics] = []
        self._metrics_thread = None
        self._inference_threads: List[threading.Thread] = []
        self._lock = threading.Lock()
        
        # Frame processing interval per camera
        self.frame_interval = 1.0 / config.inference_fps if config.inference_fps > 0 else 0
    
    def start(self):
        if not DETECTOR_AVAILABLE:
            raise RuntimeError("Detector not available. Install ultralytics and dependencies.")
        
        print(f"Loading model: {self.config.model_path}")
        self.detector = SafetyDetector(
            self.config.model_path,
            confidence=self.config.confidence,
            iou=self.config.iou
        )
        print("Model loaded successfully")
        
        self.running = True
        
        # Start system metrics collection
        self._metrics_thread = threading.Thread(target=self._collect_metrics, daemon=True)
        self._metrics_thread.start()
        
        # Start inference thread per camera
        for source in self.sources:
            t = threading.Thread(target=self._inference_loop, args=(source,), daemon=True)
            t.start()
            self._inference_threads.append(t)
    
    def stop(self):
        self.running = False
        for t in self._inference_threads:
            t.join(timeout=2)
        if self._metrics_thread:
            self._metrics_thread.join(timeout=1)
    
    def _collect_metrics(self):
        """Collect system metrics periodically"""
        process = psutil.Process() if PSUTIL_AVAILABLE else None
        
        while self.running:
            try:
                metrics = SystemMetrics(
                    timestamp=time.time(),
                    cpu_percent=psutil.cpu_percent(interval=0.1) if PSUTIL_AVAILABLE else 0,
                    ram_used_mb=psutil.virtual_memory().used / 1024 / 1024 if PSUTIL_AVAILABLE else 0,
                    ram_percent=psutil.virtual_memory().percent if PSUTIL_AVAILABLE else 0,
                )
                
                # GPU metrics
                if GPUTIL_AVAILABLE:
                    try:
                        gpus = GPUtil.getGPUs()
                        if gpus:
                            gpu = gpus[0]  # Primary GPU
                            metrics.gpu_percent = gpu.load * 100
                            metrics.vram_used_mb = gpu.memoryUsed
                            metrics.vram_percent = gpu.memoryUtil * 100
                    except:
                        pass
                
                with self._lock:
                    self.system_metrics.append(metrics)
            except Exception as e:
                print(f"Metrics collection error: {e}")
            
            time.sleep(1.0)  # Collect every second
    
    def _inference_loop(self, source: VideoSource):
        last_inference = 0
        
        while self.running:
            frame = source.get_frame(timeout=0.1)
            if frame is None:
                time.sleep(0.01)
                continue
            
            now = time.time()
            # Rate limiting per camera
            if self.frame_interval > 0 and now - last_inference < self.frame_interval:
                # Frame arrives faster than we can process - drop it (backpressure)
                source.stats.frames_dropped += 1
                continue
            
            last_inference = now
            
            # Run inference
            infer_start = time.perf_counter()
            try:
                detections = self.detector.infer(frame)
                source.stats.frames_processed += 1
                source.stats.inference_times.append(time.perf_counter() - infer_start)
                
                # Assess risk
                risk = assess_risk(detections)
                
                # Log high/critical risks
                if risk["level"] in ("high", "critical"):
                    print(f"  [Cam {source.camera_id}] RISK: {risk['level']} - {len(risk['pairs'])} pairs")
                    
            except Exception as e:
                source.stats.errors += 1
                print(f"Camera {source.camera_id} inference error: {e}")
    
    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            metrics = self.system_metrics.copy()
        
        total_received = sum(s.stats.frames_received for s in self.sources)
        total_processed = sum(s.stats.frames_processed for s in self.sources)
        total_dropped = sum(s.stats.frames_dropped for s in self.sources)
        total_errors = sum(s.stats.errors for s in self.sources)
        
        all_inference_times = []
        for s in self.sources:
            all_inference_times.extend(s.stats.inference_times)
        
        return {
            "config": asdict(self.config),
            "cameras": [
                {
                    "camera_id": s.camera_id,
                    "frames_received": s.stats.frames_received,
                    "frames_processed": s.stats.frames_processed,
                    "frames_dropped": s.stats.frames_dropped,
                    "errors": s.stats.errors,
                    "avg_inference_ms": np.mean(s.stats.inference_times) * 1000 if s.stats.inference_times else 0,
                    "p95_inference_ms": np.percentile(s.stats.inference_times, 95) * 1000 if s.stats.inference_times else 0,
                    "effective_fps": s.stats.frames_processed / self.config.duration_seconds if self.config.duration_seconds > 0 else 0,
                }
                for s in self.sources
            ],
            "aggregate": {
                "total_frames_received": total_received,
                "total_frames_processed": total_processed,
                "total_frames_dropped": total_dropped,
                "total_errors": total_errors,
                "avg_inference_ms": np.mean(all_inference_times) * 1000 if all_inference_times else 0,
                "p50_inference_ms": np.percentile(all_inference_times, 50) * 1000 if all_inference_times else 0,
                "p95_inference_ms": np.percentile(all_inference_times, 95) * 1000 if all_inference_times else 0,
                "p99_inference_ms": np.percentile(all_inference_times, 99) * 1000 if all_inference_times else 0,
                "overall_fps": total_processed / self.config.duration_seconds if self.config.duration_seconds > 0 else 0,
            },
            "system": {
                "avg_cpu_percent": np.mean([m.cpu_percent for m in metrics]) if metrics else 0,
                "peak_cpu_percent": np.max([m.cpu_percent for m in metrics]) if metrics else 0,
                "avg_ram_mb": np.mean([m.ram_used_mb for m in metrics]) if metrics else 0,
                "peak_ram_mb": np.max([m.ram_used_mb for m in metrics]) if metrics else 0,
                "avg_gpu_percent": np.mean([m.gpu_percent for m in metrics]) if metrics else 0,
                "peak_gpu_percent": np.max([m.gpu_percent for m in metrics]) if metrics else 0,
                "avg_vram_mb": np.mean([m.vram_used_mb for m in metrics]) if metrics else 0,
                "peak_vram_mb": np.max([m.vram_used_mb for m in metrics]) if metrics else 0,
            },
            "hardware": get_hardware_info(),
        }


def get_hardware_info() -> Dict[str, Any]:
    """Collect hardware information"""
    info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "cpu_freq_mhz": psutil.cpu_freq().max if PSUTIL_AVAILABLE and psutil.cpu_freq() else 0,
        "ram_total_gb": round(psutil.virtual_memory().total / 1024 / 1024 / 1024, 2) if PSUTIL_AVAILABLE else 0,
    }
    
    if TORCH_AVAILABLE:
        info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["cuda_version"] = torch.version.cuda
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["gpu_count"] = torch.cuda.device_count()
    
    if GPUTIL_AVAILABLE:
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                info["gpus"] = [
                    {"name": g.name, "memory_mb": g.memoryTotal, "driver": g.driver}
                    for g in gpus
                ]
        except:
            pass
    
    return info


def create_sources(config: BenchmarkConfig) -> List[VideoSource]:
    """Create video sources based on config"""
    sources = []
    
    if config.source_type == "synthetic":
        for i in range(config.num_cameras):
            sources.append(SyntheticSource(i, config))
    
    elif config.source_type == "rtsp":
        urls = config.source_urls or [f"rtsp://camera{i}" for i in range(config.num_cameras)]
        for i, url in enumerate(urls[:config.num_cameras]):
            sources.append(RTSPSource(i, config, url))
    
    elif config.source_type == "webcam":
        for i in range(min(config.num_cameras, 4)):  # Limit webcams
            sources.append(WebcamSource(i, config, i))
    
    elif config.source_type == "video":
        urls = config.source_urls or []
        for i, url in enumerate(urls[:config.num_cameras]):
            sources.append(VideoFileSource(i, config, url))
        # Fill remaining with synthetic
        while len(sources) < config.num_cameras:
            sources.append(SyntheticSource(len(sources), config))
    
    return sources


def run_benchmark(config: BenchmarkConfig) -> Dict[str, Any]:
    """Run the benchmark"""
    print(f"\n{'='*60}")
    print(f"EdgeSecurity Multi-Camera Benchmark")
    print(f"{'='*60}")
    print(f"Cameras: {config.num_cameras}")
    print(f"Duration: {config.duration_seconds}s")
    print(f"Source: {config.source_type}")
    print(f"Target inference FPS: {config.inference_fps}")
    print(f"Resolution: {config.resolution}")
    print(f"Model: {config.model_path}")
    print(f"Confidence: {config.confidence}, IoU: {config.iou}")
    print(f"{'='*60}\n")
    
    # Create sources
    sources = create_sources(config)
    
    # Start all sources
    for s in sources:
        s.start()
    
    # Give sources time to start
    time.sleep(2)
    
    # Create and start inference worker
    worker = InferenceWorker(config, sources)
    worker.start()
    
    # Run for duration
    print(f"Running benchmark for {config.duration_seconds} seconds...")
    start_time = time.time()
    try:
        while time.time() - start_time < config.duration_seconds:
            elapsed = time.time() - start_time
            remaining = config.duration_seconds - elapsed
            if int(elapsed) % 10 == 0 and elapsed > 1:
                print(f"  Progress: {elapsed:.0f}/{config.duration_seconds}s (remaining: {remaining:.0f}s)")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    
    # Stop everything
    print("Stopping benchmark...")
    worker.stop()
    for s in sources:
        s.stop()
    
    # Collect results
    print("Collecting results...")
    return worker.get_summary()


def save_results(results: Dict[str, Any], output_dir: str):
    """Save benchmark results to files"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON results
    json_path = os.path.join(output_dir, f"benchmark_{timestamp}.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Results saved to {json_path}")
    
    # CSV summary
    csv_path = os.path.join(output_dir, f"benchmark_{timestamp}_summary.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Value"])
        
        # Hardware
        hw = results.get("hardware", {})
        writer.writerow(["Platform", hw.get("platform", "")])
        writer.writerow(["CPU Cores", hw.get("cpu_count", "")])
        writer.writerow(["RAM (GB)", hw.get("ram_total_gb", "")])
        writer.writerow(["CUDA Available", hw.get("cuda_available", "")])
        writer.writerow(["GPU", hw.get("gpu_name", "")])
        
        writer.writerow([])
        writer.writerow(["Config", ""])
        cfg = results.get("config", {})
        for k, v in cfg.items():
            writer.writerow([k, v])
        
        writer.writerow([])
        writer.writerow(["Aggregate Results", ""])
        agg = results.get("aggregate", {})
        for k, v in agg.items():
            writer.writerow([k, v])
        
        writer.writerow([])
        writer.writerow(["System Metrics", ""])
        sys_m = results.get("system", {})
        for k, v in sys_m.items():
            writer.writerow([k, v])
        
        writer.writerow([])
        writer.writerow(["Per-Camera Results", ""])
        writer.writerow(["Camera", "Received", "Processed", "Dropped", "Errors", "Avg Inference (ms)", "P95 Inference (ms)", "Effective FPS"])
        for cam in results.get("cameras", []):
            writer.writerow([
                cam["camera_id"],
                cam["frames_received"],
                cam["frames_processed"],
                cam["frames_dropped"],
                cam["errors"],
                f"{cam['avg_inference_ms']:.2f}",
                f"{cam['p95_inference_ms']:.2f}",
                f"{cam['effective_fps']:.2f}",
            ])
    
    print(f"CSV summary saved to {csv_path}")
    
    # Print summary table
    print_summary_table(results)


def print_summary_table(results: Dict[str, Any]):
    """Print formatted summary table"""
    print(f"\n{'='*80}")
    print(f"BENCHMARK RESULTS SUMMARY")
    print(f"{'='*80}")
    
    hw = results.get("hardware", {})
    print(f"Hardware: {hw.get('platform', 'Unknown')}")
    print(f"CPU: {hw.get('cpu_count', '?')} cores @ {hw.get('cpu_freq_mhz', 0):.0f} MHz")
    print(f"RAM: {hw.get('ram_total_gb', 0):.1f} GB")
    print(f"CUDA: {hw.get('cuda_available', False)}")
    if hw.get("gpu_name"):
        print(f"GPU: {hw['gpu_name']}")
    
    print(f"\nConfig: {results['config']['num_cameras']} cameras, {results['config']['duration_seconds']}s, "
          f"{results['config']['inference_fps']} FPS target")
    
    agg = results.get("aggregate", {})
    print(f"\nAggregate:")
    print(f"  Frames Received:  {agg.get('total_frames_received', 0):,}")
    print(f"  Frames Processed: {agg.get('total_frames_processed', 0):,}")
    print(f"  Frames Dropped:   {agg.get('total_frames_dropped', 0):,} ({agg.get('total_frames_dropped', 0)/max(1,agg.get('total_frames_received',1))*100:.1f}%)")
    print(f"  Errors:           {agg.get('total_errors', 0):,}")
    print(f"  Overall FPS:      {agg.get('overall_fps', 0):.2f}")
    print(f"  Avg Inference:    {agg.get('avg_inference_ms', 0):.2f} ms")
    print(f"  P50 Inference:    {agg.get('p50_inference_ms', 0):.2f} ms")
    print(f"  P95 Inference:    {agg.get('p95_inference_ms', 0):.2f} ms")
    print(f"  P99 Inference:    {agg.get('p99_inference_ms', 0):.2f} ms")
    
    sys_m = results.get("system", {})
    print(f"\nSystem:")
    print(f"  CPU:     avg={sys_m.get('avg_cpu_percent', 0):.1f}%  peak={sys_m.get('peak_cpu_percent', 0):.1f}%")
    print(f"  RAM:     avg={sys_m.get('avg_ram_mb', 0):.0f} MB  peak={sys_m.get('peak_ram_mb', 0):.0f} MB")
    print(f"  GPU:     avg={sys_m.get('avg_gpu_percent', 0):.1f}%  peak={sys_m.get('peak_gpu_percent', 0):.1f}%")
    print(f"  VRAM:    avg={sys_m.get('avg_vram_mb', 0):.0f} MB  peak={sys_m.get('peak_vram_mb', 0):.0f} MB")
    
    print(f"\nPer-Camera:")
    print(f"  {'Cam':>4}  {'Recv':>8}  {'Proc':>8}  {'Drop':>8}  {'Err':>5}  {'Avg ms':>8}  {'P95 ms':>8}  {'Eff FPS':>8}")
    for cam in results.get("cameras", []):
        print(f"  {cam['camera_id']:>4}  {cam['frames_received']:>8}  {cam['frames_processed']:>8}  "
              f"{cam['frames_dropped']:>8}  {cam['errors']:>5}  {cam['avg_inference_ms']:>8.2f}  "
              f"{cam['p95_inference_ms']:>8.2f}  {cam['effective_fps']:>8.2f}")
    
    print(f"{'='*80}")


def main():
    parser = argparse.ArgumentParser(description="EdgeSecurity Multi-Camera Benchmark")
    parser.add_argument("--cameras", type=int, default=4, help="Number of cameras to simulate")
    parser.add_argument("--duration", type=int, default=30, help="Benchmark duration in seconds")
    parser.add_argument("--source", choices=["synthetic", "rtsp", "webcam", "video"], 
                        default="synthetic", help="Video source type")
    parser.add_argument("--urls", nargs="*", help="RTSP URLs or video file paths")
    parser.add_argument("--model", default="backend/model/edgev1.pt", help="YOLO model path")
    parser.add_argument("--confidence", type=float, default=0.4, help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=0.5, help="IoU threshold")
    parser.add_argument("--fps", type=int, default=8, help="Target inference FPS per camera")
    parser.add_argument("--width", type=int, default=640, help="Frame width")
    parser.add_argument("--height", type=int, default=480, help="Frame height")
    parser.add_argument("--output", default="benchmark_results", help="Output directory")
    
    args = parser.parse_args()
    
    config = BenchmarkConfig(
        num_cameras=args.cameras,
        duration_seconds=args.duration,
        source_type=args.source,
        source_urls=args.urls or [],
        model_path=args.model,
        confidence=args.confidence,
        iou=args.iou,
        inference_fps=args.fps,
        resolution=(args.width, args.height),
        output_dir=args.output,
    )
    
    try:
        results = run_benchmark(config)
        save_results(results, config.output_dir)
        
        # Print conclusion
        agg = results.get("aggregate", {})
        sys_m = results.get("system", {})
        print(f"\nCONCLUSION:")
        print(f"  Stable cameras: {config.num_cameras}")
        print(f"  Overall FPS: {agg.get('overall_fps', 0):.2f}")
        print(f"  Avg inference: {agg.get('avg_inference_ms', 0):.2f} ms")
        print(f"  Peak CPU: {sys_m.get('peak_cpu_percent', 0):.1f}%")
        print(f"  Peak RAM: {sys_m.get('peak_ram_mb', 0):.0f} MB")
        if sys_m.get('peak_gpu_percent', 0) > 0:
            print(f"  Peak GPU: {sys_m['peak_gpu_percent']:.1f}%")
        
    except Exception as e:
        print(f"Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()