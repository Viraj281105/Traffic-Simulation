import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ API_BASE_URL: "" }));
vi.mock("../auth/cognito", () => ({ getAuthToken: () => Promise.resolve("") }));

import { failWith, stubApi } from "../insights/testApi";
import { MAX_UPLOAD_BYTES, validateNetworkFile } from "./api";
import { invalidFixture, previewFixture, validationFixture } from "./fixtures";
import { MessageList } from "./MessageList";
import { sortMessages } from "./messages";
import { NetworkUpload } from "./NetworkUpload";
import { PreviewMap, RoadImportPreview } from "./RoadImportPreview";
import { parseArea } from "./roadImport";
import { precheckFile } from "./uploadChecks";

afterEach(() => {
  vi.unstubAllGlobals();
});

const file = (name = "corridor.net.xml", body = "<net/>") =>
  new File([body], name, { type: "text/xml" });

describe("messages", () => {
  it("lists errors before warnings before notes", () => {
    const order = sortMessages([
      ...validationFixture.messages,
      ...invalidFixture.messages,
    ]).map((m) => m.severity);
    expect(order).toEqual(["error", "warning", "warning", "info"]);
  });

  it("spells out severity, location and hint", () => {
    render(<MessageList messages={invalidFixture.messages} />);
    const first = screen.getAllByRole("listitem")[0];
    expect(first).toHaveTextContent("Error: Road 12 ends at a junction");
    expect(first).toHaveTextContent("line 48, element way_12");
    expect(first).toHaveTextContent("Export a slightly larger area");
  });
});

describe("precheckFile", () => {
  it("refuses an empty or oversized file before upload", () => {
    expect(precheckFile(file("a.osm", ""))[0]?.code).toBe("empty_file");
    const big = file();
    Object.defineProperty(big, "size", { value: MAX_UPLOAD_BYTES + 1 });
    expect(precheckFile(big)[0]?.code).toBe("file_too_large");
    expect(precheckFile(file())).toEqual([]);
  });
});

describe("validateNetworkFile", () => {
  it("posts the file and format as multipart form data", async () => {
    const { calls } = stubApi({
      "POST /api/v3/networks/validate": validationFixture,
    });
    const result = await validateNetworkFile(file(), "sumo");
    expect(result.valid).toBe(true);
    const body = calls[0]?.init?.body as FormData;
    expect(body.get("format")).toBe("sumo");
    expect((body.get("file") as File).name).toBe("corridor.net.xml");
  });

  it("raises the server's reason for a refused upload", async () => {
    stubApi({
      "POST /api/v3/networks/validate": failWith(415, "Unsupported file type"),
    });
    await expect(validateNetworkFile(file())).rejects.toThrow(
      "Unsupported file type",
    );
  });
});

describe("NetworkUpload", () => {
  it("validates a chosen file and shows the summary and messages", async () => {
    stubApi({ "POST /api/v3/networks/validate": invalidFixture });
    render(<NetworkUpload />);
    const button = screen.getByRole("button", { name: /Check file/ });
    expect(button).toBeDisabled();
    await userEvent.upload(
      screen.getByLabelText("Network file"),
      file("broken.osm"),
    );
    await userEvent.click(button);
    expect(
      await screen.findByText("This network cannot be used yet"),
    ).toBeInTheDocument();
    expect(screen.getByText("Not valid")).toBeInTheDocument();
    expect(screen.getByText(/1 error, 1 warning/)).toBeInTheDocument();
    expect(screen.getByText(/Road 12 ends at a junction/)).toBeInTheDocument();
  });

  it("shows summary figures for a valid network", async () => {
    stubApi({ "POST /api/v3/networks/validate": validationFixture });
    render(<NetworkUpload />);
    await userEvent.upload(screen.getByLabelText("Network file"), file());
    await userEvent.click(screen.getByRole("button", { name: /Check file/ }));
    expect(
      await screen.findByText("This network can be used"),
    ).toBeInTheDocument();
    expect(screen.getByText("3.4")).toBeInTheDocument();
    expect(
      screen.getByText(/Pedestrian crossings are not modelled/),
    ).toBeInTheDocument();
  });

  it("shows a refused upload as an error message", async () => {
    stubApi({
      "POST /api/v3/networks/validate": failWith(413, "File is too large"),
    });
    render(<NetworkUpload />);
    await userEvent.upload(screen.getByLabelText("Network file"), file());
    await userEvent.click(screen.getByRole("button", { name: /Check file/ }));
    expect(await screen.findByText(/File is too large/)).toBeInTheDocument();
  });
});

describe("parseArea", () => {
  it("reads a box or a place name, and rejects an impossible box", () => {
    expect(parseArea("-1.56, 53.79, -1.53, 53.81")).toEqual({
      bbox: [-1.56, 53.79, -1.53, 53.81],
    });
    expect(parseArea("Leeds city centre")).toEqual({
      place: "Leeds city centre",
    });
    expect(parseArea("5, 1, 2, 3")).toBeNull();
    expect(parseArea("  ")).toBeNull();
  });
});

describe("RoadImportPreview", () => {
  it("sends the area and road types and shows stats, map and messages", async () => {
    const { calls } = stubApi({
      "POST /api/v3/networks/import/preview": previewFixture,
    });
    render(<RoadImportPreview />);
    const run = screen.getByRole("button", { name: /Preview import/ });
    expect(run).toBeDisabled();
    await userEvent.type(
      screen.getByLabelText("Place name or box"),
      "Leeds city centre",
    );
    await userEvent.click(screen.getByLabelText("Residential"));
    await userEvent.click(run);
    expect(
      await screen.findByRole("img", { name: /Preview of 2 roads in Leeds/ }),
    ).toBeInTheDocument();
    expect(JSON.parse(calls[0]?.init?.body as string)).toEqual({
      source: "osm",
      place: "Leeds city centre",
      roadClasses: ["primary", "secondary", "tertiary", "residential"],
    });
    expect(screen.getByText("21.7")).toBeInTheDocument();
    expect(screen.getByText(/one lane was assumed/)).toBeInTheDocument();
    expect(screen.getByText(/Showing 2 of 190 roads/)).toBeInTheDocument();
  });

  it("explains an invalid box and needs at least one road type", async () => {
    render(<RoadImportPreview />);
    await userEvent.type(screen.getByLabelText("Place name or box"), "5,1,2,3");
    expect(screen.getByRole("alert")).toHaveTextContent("not valid");
    await userEvent.clear(screen.getByLabelText("Place name or box"));
    await userEvent.type(screen.getByLabelText("Place name or box"), "Leeds");
    const types = screen.getByRole("group", { name: "Road types" });
    for (const box of within(types).getAllByRole("checkbox")) {
      if ((box as HTMLInputElement).checked) await userEvent.click(box);
    }
    expect(
      screen.getByRole("button", { name: /Preview import/ }),
    ).toBeDisabled();
  });

  it("draws one line per road", () => {
    const { container } = render(<PreviewMap preview={previewFixture} />);
    expect(container.querySelectorAll("polyline")).toHaveLength(2);
  });
});
