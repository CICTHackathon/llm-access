import { getToken } from "next-auth/jwt"
import { NextResponse, type NextRequest } from "next/server"

// Sign-in gate only. Roles are not checked here: the session cookie keeps the role from
// sign-in time, so a role change would apply late. Every page (requirePage) and API route
// (requireApi) checks the current role from the database instead.
export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl
  const signedIn = !!(await getToken({ req }))?.role

  if (pathname.startsWith("/signin")) {
    return signedIn ? NextResponse.redirect(new URL("/dashboard", req.url)) : NextResponse.next()
  }
  if (signedIn) return NextResponse.next()
  if (pathname.startsWith("/api/")) return NextResponse.json({ error: "Sign in required" }, { status: 401 })
  const url = new URL("/signin", req.url)
  url.searchParams.set("callbackUrl", pathname)
  return NextResponse.redirect(url)
}

export const config = {
  matcher: ["/dashboard/:path*", "/signin", "/api/((?!auth/).*)"],
}
