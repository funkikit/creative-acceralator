import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const COOKIE_NAME = "poc-auth";

export async function POST() {
  cookies().set({
    name: COOKIE_NAME,
    value: "",
    expires: new Date(0),
    path: "/",
  });
  return NextResponse.json({ ok: true });
}
