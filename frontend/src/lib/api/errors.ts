export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(args: { status: number; detail?: string; message: string }) {
    super(args.message);
    this.status = args.status;
    this.detail = args.detail;
  }
}

