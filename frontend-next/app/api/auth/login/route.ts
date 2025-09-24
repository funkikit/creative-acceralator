import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const COOKIE_NAME = "poc-auth";
const MAX_AGE = 60 * 60 * 8; // 8 hours

export async function POST(request: Request) {
  try {
    const { password } = await request.json();
    const expected = process.env.POC_ACCESS_PASSWORD;

    if (!expected) {
      return NextResponse.json({ message: "サーバー側にパスワードが設定されていません" }, { status: 500 });
    }

    if (!password) {
      return NextResponse.json({ message: "パスワードを入力してください" }, { status: 400 });
    }

    if (password !== expected) {
      return NextResponse.json({ message: "パスワードが一致しません" }, { status: 401 });
    }

    const secure = process.env.NODE_ENV === "production";

    cookies().set({
      name: COOKIE_NAME,
      value: "ok",
      httpOnly: true,
      sameSite: "lax",
      secure,
      maxAge: MAX_AGE,
      path: "/",
    });

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("/api/auth/login", error);
    return NextResponse.json({ message: "予期しないエラーが発生しました" }, { status: 500 });
  }
}
