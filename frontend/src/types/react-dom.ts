declare module "react-dom" {
  // Minimal typing to unblock `next build` when upstream types are missing.
  // We only need `createPortal` in our UI.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  export function createPortal(children: any, container: any): any;
}

