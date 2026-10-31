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
