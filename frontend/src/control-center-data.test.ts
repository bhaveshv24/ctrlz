import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import { loadWorkspace, loadWorkspaceMetadata } from "./control-center-data";

vi.mock("./api", async (original) => ({
  ...await original<typeof import("./api")>(),
  api: vi.fn(),
}));
const request = vi.mocked(api);
const overview = {projects: [], summary: {open_incidents: 0}};

beforeEach(() => { request.mockReset(); });
describe("sign-in when health metadata is unavailable", () => {
  it("opens the private workspace without requesting health", async () => {
    request.mockImplementation(async (path) => {
      if (path === "/overview") return overview;
      if (path === "/incidents") return [];
      throw new TypeError("NetworkError when attempting to fetch resource");
    });
    expect(await loadWorkspace("valid-session")).toEqual({overview, incidents: []});
    expect(request.mock.calls.map(([path]) => path)).toEqual(["/overview", "/incidents"]);
  });

  it("degrades unavailable health and demo panels without rejecting the session", async () => {
    request.mockRejectedValue(new TypeError("NetworkError when attempting to fetch resource"));
    expect(await loadWorkspaceMetadata("valid-session")).toEqual({runtime: null, runs: []});
  });

  it("continues to reject unauthorized access to private workspace records", async () => {
    request.mockRejectedValue(new ApiError("Session expired", 401));
    await expect(loadWorkspace("expired-session")).rejects.toMatchObject({status: 401});
  });

  it("can load metadata again after the endpoint recovers", async () => {
    const runtime = {provider: "NVIDIA NIM", nim_configured: true};
    request.mockRejectedValueOnce(new TypeError("Network failure")).mockResolvedValueOnce([]);
    expect((await loadWorkspaceMetadata("valid-session")).runtime).toBeNull();
    request.mockImplementation(async (path) => path === "/health" ? runtime : []);
    expect(await loadWorkspaceMetadata("valid-session")).toEqual({runtime, runs: []});
  });
});
