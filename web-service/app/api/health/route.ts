/**
 * Health Check API Route
 *
 * Used by Docker healthcheck and monitoring.
 */

import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    status: "healthy",
    timestamp: new Date().toISOString(),
    service: "Trollama Web Service",
    version: "1.0.0",
  });
}
