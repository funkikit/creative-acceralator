import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const COOKIE_NAME = "poc-auth";

const PUBLIC_PREFIXES = [
  "/login",
  "/_next",
  "/favicon.ico",
  "/static",
  "/api/auth/login",
  "/api/auth/logout",
].map((path) => path.toLowerCase());

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const lowerPath = pathname.toLowerCase();

  const isPublic = PUBLIC_PREFIXES.some((prefix) => lowerPath.startsWith(prefix));
  const hasCookie = request.cookies.get(COOKIE_NAME)?.value === "ok";

  if (!hasCookie && !isPublic) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (hasCookie && lowerPath.startsWith("/login")) {
    const next = request.nextUrl.searchParams.get("next") ?? "/creative";
    return NextResponse.redirect(new URL(next, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/(.*)"],
};
