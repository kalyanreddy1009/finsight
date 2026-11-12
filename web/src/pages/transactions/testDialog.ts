// jsdom may not implement <dialog> showModal/close. This stub keeps the open attribute in sync.
export function installDialogStub(): void {
  const proto = HTMLDialogElement.prototype;
  if (typeof proto.showModal === "function") {
    return;
  }
  proto.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  proto.close = function close(this: HTMLDialogElement) {
    if (!this.hasAttribute("open")) {
      return;
    }
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
}
