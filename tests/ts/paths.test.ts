/**
 * Unit tests for TypeScript path normalization.
 *
 * These must match the behavior of sidecar/services/paths.py exactly.
 * Cross-platform path handling is critical for frontmatter and graph.json.
 */

import { describe, it, expect } from "vitest";
import {
  normalizePath,
  toRelative,
  isCleanVaultPath,
  isWikiVaultPath,
} from "@/api/paths";

describe("normalizePath", () => {
  it("converts backslashes to forward slashes", () => {
    expect(normalizePath("clean-vault\\raw\\paper.md")).toBe(
      "clean-vault/raw/paper.md",
    );
  });

  it("leaves forward slashes unchanged", () => {
    expect(normalizePath("clean-vault/raw/paper.md")).toBe(
      "clean-vault/raw/paper.md",
    );
  });

  it("handles mixed slashes", () => {
    expect(normalizePath("clean-vault\\raw/paper.md")).toBe(
      "clean-vault/raw/paper.md",
    );
  });

  it("handles empty string", () => {
    expect(normalizePath("")).toBe("");
  });

  it("handles single filename", () => {
    expect(normalizePath("paper.md")).toBe("paper.md");
  });

  it("handles deep nesting", () => {
    expect(normalizePath("a\\b\\c\\d\\e\\f.md")).toBe("a/b/c/d/e/f.md");
  });
});

describe("toRelative", () => {
  it("extracts relative path from absolute", () => {
    const result = toRelative(
      "C:/Users/User/Vanilla/clean-vault/raw/paper.md",
      "C:/Users/User/Vanilla",
    );
    expect(result).toBe("clean-vault/raw/paper.md");
  });

  it("handles trailing slash on root", () => {
    const result = toRelative(
      "C:/Users/User/Vanilla/wiki-vault/concepts/topic.md",
      "C:/Users/User/Vanilla/",
    );
    expect(result).toBe("wiki-vault/concepts/topic.md");
  });

  it("returns full path if not a child of root", () => {
    const result = toRelative(
      "/other/path/file.md",
      "/home/user/Vanilla",
    );
    expect(result).toBe("/other/path/file.md");
  });
});

describe("isCleanVaultPath", () => {
  it("detects clean vault paths", () => {
    expect(isCleanVaultPath("clean-vault/raw/paper.md")).toBe(true);
    expect(isCleanVaultPath("clean-vault/notes/note.md")).toBe(true);
  });

  it("rejects wiki vault paths", () => {
    expect(isCleanVaultPath("wiki-vault/concepts/topic.md")).toBe(false);
  });

  it("handles backslashes", () => {
    expect(isCleanVaultPath("clean-vault\\raw\\paper.md")).toBe(true);
  });
});

describe("isWikiVaultPath", () => {
  it("detects wiki vault paths", () => {
    expect(isWikiVaultPath("wiki-vault/concepts/topic.md")).toBe(true);
    expect(isWikiVaultPath("wiki-vault/staging/batch_001/article.md")).toBe(
      true,
    );
  });

  it("rejects clean vault paths", () => {
    expect(isWikiVaultPath("clean-vault/raw/paper.md")).toBe(false);
  });
});
