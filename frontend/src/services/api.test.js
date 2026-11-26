import { afterEach, describe, expect, it, vi } from "vitest";
import {
  confirmEmailVerification,
  getAccessToken,
  getProjects,
  requestEmailVerification,
  setAccessToken,
} from "./api.js";

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken("");
});

describe("authenticated project requests", () => {
  it("requests archived projects only when explicitly selected", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken("access-token");

    await getProjects({ includeArchived: true });

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/projects?include_archived=true");
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get("Authorization"))
      .toBe("Bearer access-token");
  });

  it("retries a rejected request at most once after refreshing the session", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("{}", { status: 401 }))
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ access_token: "renewed-token", user: { id: "user-1" } }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ))
      .mockResolvedValueOnce(new Response("{}", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("document", { cookie: "contractiq_csrf=csrf-token" });
    setAccessToken("expired-token");

    await expect(getProjects()).rejects.toThrow("Backend returned HTTP 401");

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(new Headers(fetchMock.mock.calls[2][1].headers).get("Authorization"))
      .toBe("Bearer renewed-token");
    expect(getAccessToken()).toBe("");
  });
});

describe("email verification requests", () => {
  it("sends email addresses and verification tokens to their matching endpoints", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ message: "Accepted" }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await requestEmailVerification("person@example.com");
    await confirmEmailVerification("one-time-token");

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/auth/email-verification/request");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ email: "person@example.com" });
    expect(fetchMock.mock.calls[1][0]).toContain("/api/v1/auth/email-verification/confirm");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ token: "one-time-token" });
  });
});
