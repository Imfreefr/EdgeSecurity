window.EdgeLoading = {
  observers: new Map(),
  begin(id, label) {
    const target = document.getElementById(id);
    if (!target) return;
    this.observers.get(id)?.disconnect();
    target.setAttribute("aria-busy", "true");
    const status = document.createElement("div");
    status.className = "data-loading";
    status.setAttribute("role", "status");
    const text = document.createElement("span");
    text.textContent = label;
    status.append(text);
    const bars = document.createElement("span");
    bars.className = "data-loading-bars";
    bars.setAttribute("aria-hidden", "true");
    status.append(bars);
    target.replaceChildren(status);
    const observer = new MutationObserver(() => {
      if (!target.querySelector(".data-loading")) this.end(id);
    });
    observer.observe(target, {childList: true, subtree: true});
    this.observers.set(id, observer);
  },
  end(id) {
    this.observers.get(id)?.disconnect();
    this.observers.delete(id);
    const target = document.getElementById(id);
    target?.removeAttribute("aria-busy");
    target?.querySelector(".data-loading")?.remove();
  },
  fail(id) {
    this.end(id);
    const target = document.getElementById(id);
    if (!target) return;
    const status = document.createElement("div");
    status.className = "data-loading";
    status.setAttribute("role", "alert");
    status.textContent = "Não foi possível carregar os dados. ";
    const retry = document.createElement("button");
    retry.className = "btn btn-secondary";
    retry.textContent = "Tentar novamente";
    retry.onclick = () => location.reload();
    status.append(retry);
    target.replaceChildren(status);
  },
};
