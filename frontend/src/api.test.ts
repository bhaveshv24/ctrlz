import { describe, it, expect, vi, afterEach } from "vitest";
import { parseFrame, downloadRepairedZip } from "./api";
afterEach(() => vi.unstubAllGlobals());
describe("repaired repository downloads", () => {
  it("shows the server error instead of saving an error response as a ZIP", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({detail: "No verified repair"}), {status: 422})));
    await expect(downloadRepairedZip("incident", "token")).rejects.toThrow("No verified repair");
  });
  it("rejects a successful response containing a proxy error page", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>Proxy unavailable</html>")));
    await expect(downloadRepairedZip("incident", "token")).rejects.toThrow("valid repository ZIP");
  });
  it("downloads the authenticated ZIP without refreshing incident data", async () => {
    const click = vi.fn(), remove = vi.fn(), appendChild = vi.fn();
    const link = {href: "", download: "", click, remove};
    vi.stubGlobal("document", {createElement: () => link, body: {appendChild}});
    const fetch = vi.fn().mockResolvedValue(new Response(new Uint8Array([0x50, 0x4b, 3, 4, 0])));
    vi.stubGlobal("fetch", fetch);
    await downloadRepairedZip("incident", "private-token");
    expect(fetch).toHaveBeenCalledExactlyOnceWith(expect.stringContaining("/incidents/incident/repaired.zip"), {headers: {Authorization: "Bearer private-token"}});
    expect(link.download).toBe("ctrlz-incident-repaired.zip");
    expect(click).toHaveBeenCalledOnce();
    expect(remove).toHaveBeenCalledOnce();
  });
});
describe("persisted recovery event protocol", () => {
  it("ignores heartbeats", () => expect(parseFrame(": heartbeat")).toBeNull());
  it("decodes SSE event data", () =>
    expect(
      parseFrame(
        'id: 9\nevent: recovery\ndata: {"id":9,"stage":"verification"}',
      ),
    ).toEqual({ id: 9, stage: "verification" }));
});

describe("API failure recovery", () => {
  it("explains network failures without exposing browser exception text", async () => {
    const { api } = await import("./api");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api("/overview", "token")).rejects.toThrow("Couldn’t reach the server");
  });
  it("bounds requests and explains timeouts", async () => {
    const { api } = await import("./api");
    const fetch = vi.fn().mockRejectedValue(new DOMException("timeout", "TimeoutError"));
    vi.stubGlobal("fetch", fetch);
    await expect(api("/overview", "token")).rejects.toThrow("took too long");
    expect(fetch.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal);
  });
  it("retains unauthorized status for session expiry handling", async () => {
    const { api } = await import("./api");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"detail":"Session expired"}', {status:401})));
    await expect(api("/overview", "token")).rejects.toMatchObject({status:401});
  });
  it("turns proxy HTML into an actionable error", async () => {
    const { api } = await import("./api");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>upstream offline</html>")));
    await expect(api("/overview", "token")).rejects.toThrow("unexpected response");
  });
  it("renders validation details as readable messages", async () => {
    const { api } = await import("./api");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"detail":[{"msg":"Enter a valid email address"}]}', {status:422})));
    await expect(api("/auth/register", "", {})).rejects.toThrow("Enter a valid email address");
  });
});
