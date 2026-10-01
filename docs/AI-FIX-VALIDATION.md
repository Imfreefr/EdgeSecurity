# AI integration corrections

Verified against the tracked INT8 ONNX protobuf metadata:
- input: float32 [1, 3, 640, 640]
- output: float32 [1, 300, 6] (end-to-end detections)
- classes: .pessoa, .máquina, operador, objeto
- model description: Ultralytics YOLO26n

Corrections:
- resolve the Worker relative to the loaded script, independent of page URL;
- keep at most one pending frame in both browser and WebSocket clients;
- throttle local alerts per camera/level for 30 seconds and surface persistence errors;
- validate output dimensions explicitly and preserve generic objects as objects;
- use letterbox padding 114;
- authenticate WebSocket via first message (10-second deadline), validate active user,
  subscription, permission, tenant and camera assignment on connection and every frame;
- reject changing cameras mid-connection, oversized images and disallowed origins;
- stop the local worker before falling back to the local backend;
- copy the model during ESM builds without relying on __dirname.

Validation:
- node tests/ai-pipeline.mjs: passed (Worker URL, frame bound, cooldown, shutdown).
- python tests/test_ws_authorization.py: passed (missing auth, invalid token,
  foreign camera, own camera). This extracts the actual endpoint and supplies
  isolated doubles for database, authentication and detector dependencies.
- JavaScript syntax and Python AST parsing: passed.
- node node_modules/vite/bin/vite.js build --configLoader runner: passed;
  INT8 model copied to dist/assets.

These checks do not prove live browser inference, physical camera detection,
real PostgreSQL authorization or production deployment. Those require an
end-to-end run. Earlier broad approval statements in RELATORIO_FINAL.md should
not be interpreted as evidence of those unexecuted checks.
