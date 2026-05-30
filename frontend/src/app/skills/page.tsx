"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { fetchSkills, createSkill, updateSkill, deleteSkill, evolveSkills, importSkills, exportSkills, importMarkdownSkill } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Zap, RefreshCw, CheckCircle2, XCircle, TrendingUp, Plus, Trash2, Edit3, ToggleLeft, ToggleRight, X, Save, Search, Clock, Hash, Upload, Download, FileJson, AlertCircle } from "lucide-react";

interface Skill {
  id: number; name: string; description: string; instruction: string;
  success_count: number; fail_count: number; version: number;
  is_active: boolean; created_at: string; updated_at: string;
}

const inputStyle: React.CSSProperties = {
  width: "100%", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)",
  borderRadius: 8, padding: "10px 14px", fontSize: 14, color: "var(--color-text-primary)", outline: "none",
};

export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [evolving, setEvolving] = useState(false);
  const [selected, setSelected] = useState<Skill | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editInstruction, setEditInstruction] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [newSkill, setNewSkill] = useState({ name: "", description: "", instruction: "" });
  const [evolveResult, setEvolveResult] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<"all" | "active" | "inactive">("all");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [importText, setImportText] = useState("");
  const [importOverwrite, setImportOverwrite] = useState(false);
  const [importPreview, setImportPreview] = useState<{ name: string; description: string; instruction: string }[] | null>(null);
  const [importError, setImportError] = useState("");
  const [importResult, setImportResult] = useState<{ imported: { name: string; action: string }[]; skipped: { name: string; reason: string }[]; errors: { name: string; error: string }[] } | null>(null);
  const [importing, setImporting] = useState(false);
  const [importFormat, setImportFormat] = useState<"json" | "markdown">("json");
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { load(); }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await fetchSkills();
      setSkills(d.skills || []);
    } catch {} finally { setLoading(false); }
  }, []);

  const handleEvolve = async () => {
    setEvolving(true);
    setEvolveResult("");
    try {
      const d = await evolveSkills();
      const count = d.evolved?.length || 0;
      setEvolveResult(count > 0 ? `${count} skill(s) evolved successfully` : "No skills needed evolution");
      await load();
    } catch { setEvolveResult("Evolution failed"); }
    finally { setEvolving(false); }
  };

  const handleCreate = async () => {
    if (!newSkill.name.trim() || !newSkill.description.trim() || !newSkill.instruction.trim()) return;
    try {
      await createSkill(newSkill);
      setShowCreate(false);
      setNewSkill({ name: "", description: "", instruction: "" });
      await load();
    } catch {}
  };

  const handleToggle = async (skill: Skill) => {
    try {
      await updateSkill(skill.name, { is_active: !skill.is_active });
      await load();
      if (selected?.name === skill.name) setSelected({ ...skill, is_active: !skill.is_active });
    } catch {}
  };

  const handleDelete = async (name: string) => {
    try {
      await deleteSkill(name);
      if (selected?.name === name) setSelected(null);
      setConfirmDelete(null);
      await load();
    } catch {}
  };

  const handleSaveInstruction = async () => {
    if (!selected) return;
    try {
      await updateSkill(selected.name, { description: editDescription, instruction: editInstruction });
      setEditing(false);
      await load();
    } catch {}
  };

  const rate = (s: Skill) => { const t = s.success_count + s.fail_count; return t === 0 ? 0 : Math.round((s.success_count / t) * 100); };

  const detectImportFormat = (text: string, fileName: string = ""): "json" | "markdown" => {
    const lowerName = fileName.toLowerCase();
    if (lowerName.endsWith(".md") || lowerName.endsWith(".markdown") || lowerName.endsWith(".txt")) {
      return "markdown";
    }

    const trimmed = text.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      return "json";
    }

    return "markdown";
  };

  const parseImportData = (text: string, format: "json" | "markdown"): { name: string; description: string; instruction: string }[] => {
    const trimmed = text.trim();
    if (!trimmed) return [];

    if (format === "markdown") {
      // Parse Markdown skill with YAML frontmatter
      const result = parseMarkdownSkill(trimmed);
      return result ? [result] : [];
    }

    const data = JSON.parse(trimmed);
    // Support both single object and array
    const items = Array.isArray(data) ? data : [data];
    // Also support { skills: [...] } wrapper format
    const list = items.length === 1 && items[0].skills && Array.isArray(items[0].skills) ? items[0].skills : items;
    return list.filter((s: any) => s.name && s.instruction).map((s: any) => ({
      name: String(s.name),
      description: String(s.description || ""),
      instruction: String(s.instruction || ""),
    }));
  };

  const parseMarkdownSkill = (text: string): { name: string; description: string; instruction: string } | null => {
    // Parse YAML frontmatter between --- delimiters
    let frontmatter: Record<string, string> = {};
    let body = text;

    const fmMatch = text.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
    if (fmMatch) {
      const fmText = fmMatch[1].trim();
      body = fmMatch[2].trim();
      for (const line of fmText.split("\n")) {
        const trimmed = line.trim();
        if (trimmed.includes(":")) {
          const idx = trimmed.indexOf(":");
          const key = trimmed.slice(0, idx).trim();
          const value = trimmed.slice(idx + 1).trim().replace(/^["']|["']$/g, "");
          frontmatter[key] = value;
        }
      }
    }

    let name = frontmatter.name || "";
    let description = frontmatter.description || "";

    if (!name) {
      const headingMatch = body.match(/^#\s+(.+)$/m);
      if (headingMatch) {
        name = headingMatch[1].trim().replace(/[^\w]+/g, "_").toLowerCase().replace(/^_|_$/g, "");
      }
    }

    let instruction = body;
    // Remove title heading if it matches name
    if (name && instruction.match(new RegExp(`^#\\s+.*\\n`, "m"))) {
      instruction = instruction.replace(/^#\s+.*\n/, "").trim();
    }

    // Extract "## Instruction" section if present
    const instructionMatch = instruction.match(/^##\s+Instruction\s*\n([\s\S]*)$/m);
    if (instructionMatch) {
      instruction = instructionMatch[1].trim();
    }

    if (!name) return null;

    if (!description) {
      const firstPara = instruction.match(/^(?!#)([\s\S]+?)(?:\n\n|\n#|$)/m);
      description = firstPara ? firstPara[1].trim().slice(0, 200) : name.replace(/_/g, " ");
    }

    return { name, description, instruction };
  };

  const handleImportPreview = () => {
    setImportError("");
    setImportResult(null);
    try {
      const parsed = parseImportData(importText, importFormat);
      if (parsed.length === 0) {
        setImportError(importFormat === "markdown"
          ? "No valid skill found. Markdown format needs YAML frontmatter with 'name' field or a heading."
          : "No valid skills found. Each skill needs at least 'name' and 'instruction'.");
        setImportPreview(null);
        return;
      }
      setImportPreview(parsed);
    } catch (e: any) {
      setImportError(importFormat === "markdown" ? `Invalid Markdown: ${e.message}` : `Invalid JSON: ${e.message}`);
      setImportPreview(null);
    }
  };

  const handleImportConfirm = async () => {
    if (!importPreview) return;
    setImporting(true);
    try {
      if (importFormat === "markdown") {
        // Use the markdown import API
        const result = await importMarkdownSkill(importText, importOverwrite);
        setImportResult({
          imported: result.status !== "skipped" ? [{ name: result.name || "unknown", action: result.status || "created" }] : [],
          skipped: result.status === "skipped" ? [{ name: result.name || "unknown", reason: result.reason || "already exists" }] : [],
          errors: [],
        });
      } else {
        const result = await importSkills(importPreview, importOverwrite);
        setImportResult(result);
      }
      await load();
    } catch (e: any) {
      setImportError(`Import failed: ${e.message}`);
    } finally {
      setImporting(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const inferredFormat = detectImportFormat("", file.name);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      setImportFormat(detectImportFormat(text, file.name) || inferredFormat);
      setImportText(text);
      setImportResult(null);
      setImportError("");
      setImportPreview(null);
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const handleExport = async () => {
    try {
      const data = await exportSkills();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `skills_export_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {}
  };

  const filtered = skills.filter((s) => {
    if (filterStatus === "active" && !s.is_active) return false;
    if (filterStatus === "inactive" && s.is_active) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q);
    }
    return true;
  });

  const activeCount = skills.filter((s) => s.is_active).length;
  const totalSuccess = skills.reduce((a, s) => a + s.success_count, 0);
  const totalFail = skills.reduce((a, s) => a + s.fail_count, 0);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <header style={{ height: 56, borderBottom: "1px solid var(--color-border-default)", padding: "0 24px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0, background: "var(--color-bg-elevated)" }}>
        <span style={{ fontSize: 15, fontWeight: 600 }}>Skills</span>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => setShowCreate(true)} style={{ display: "flex", alignItems: "center", gap: 6, height: 32, padding: "0 14px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 8, fontSize: 13, color: "var(--color-text-secondary)", cursor: "pointer" }}>
            <Plus size={13} /> Create
          </button>
          <button onClick={() => { setShowImport(true); setImportText(""); setImportPreview(null); setImportResult(null); setImportError(""); }} style={{ display: "flex", alignItems: "center", gap: 6, height: 32, padding: "0 14px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 8, fontSize: 13, color: "var(--color-info)", cursor: "pointer" }}>
            <Upload size={13} /> Import
          </button>
          <button onClick={handleExport} style={{ display: "flex", alignItems: "center", gap: 6, height: 32, padding: "0 14px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 8, fontSize: 13, color: "var(--color-text-secondary)", cursor: "pointer" }}>
            <Download size={13} /> Export
          </button>
          <button onClick={handleEvolve} disabled={evolving} style={{ display: "flex", alignItems: "center", gap: 6, height: 32, padding: "0 14px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 8, fontSize: 13, color: "var(--color-text-secondary)", cursor: "pointer" }}>
            <RefreshCw size={13} style={{ animation: evolving ? "spin 1s linear infinite" : "none" }} /> Evolve
          </button>
        </div>
      </header>

      {evolveResult && (
        <div style={{ padding: "8px 20px", background: "rgba(34,197,94,0.08)", borderBottom: "1px solid rgba(34,197,94,0.2)", fontSize: 13, color: "var(--color-success)", textAlign: "center" }}>
          {evolveResult}
        </div>
      )}

      {/* Create Skill Dialog */}
      {showCreate && (
        <div style={{ padding: 20, borderBottom: "1px solid var(--color-border-default)", background: "var(--color-bg-secondary)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600 }}>Create New Skill</h3>
            <button onClick={() => setShowCreate(false)} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer" }}><X size={16} /></button>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 500 }}>
            <input type="text" value={newSkill.name} onChange={(e) => setNewSkill((p) => ({ ...p, name: e.target.value }))} placeholder="Skill name (snake_case, e.g. deploy_web_app)" style={inputStyle} />
            <input type="text" value={newSkill.description} onChange={(e) => setNewSkill((p) => ({ ...p, description: e.target.value }))} placeholder="Brief description" style={inputStyle} />
            <textarea value={newSkill.instruction} onChange={(e) => setNewSkill((p) => ({ ...p, instruction: e.target.value }))} placeholder="Detailed step-by-step instruction for this skill..." rows={5} style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit" }} />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button onClick={() => setShowCreate(false)} style={{ padding: "8px 16px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 8, fontSize: 13, color: "var(--color-text-secondary)", cursor: "pointer" }}>Cancel</button>
              <button onClick={handleCreate} disabled={!newSkill.name.trim() || !newSkill.description.trim() || !newSkill.instruction.trim()} style={{ padding: "8px 16px", background: "var(--color-text-primary)", color: "var(--color-bg-primary)", border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", opacity: (!newSkill.name.trim() || !newSkill.description.trim() || !newSkill.instruction.trim()) ? 0.5 : 1 }}>Create Skill</button>
            </div>
          </div>
        </div>
      )}

      {/* Import Skill Dialog */}
      {showImport && (
        <>
          <div onClick={() => setShowImport(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 99, backdropFilter: "blur(2px)" }} />
          <div style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 12, padding: "20px 24px", width: "min(560px, 90vw)", maxHeight: "85vh", display: "flex", flexDirection: "column", boxShadow: "0 12px 40px rgba(0,0,0,0.5)", zIndex: 100 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexShrink: 0 }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                <Upload size={16} /> Import Skills
              </h3>
              <button onClick={() => setShowImport(false)} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: 18, lineHeight: 1 }}>&times;</button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 12, overflowY: "auto", flex: 1 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--color-text-muted)", display: "block", marginBottom: 6, fontWeight: 500 }}>Import Format</label>
                <div style={{ display: "flex", gap: 6 }}>
                  {(["json", "markdown"] as const).map((format) => (
                    <button
                      key={format}
                      onClick={() => { setImportFormat(format); setImportPreview(null); setImportResult(null); setImportError(""); }}
                      style={{
                        padding: "6px 12px",
                        borderRadius: 8,
                        border: "1px solid var(--color-border-default)",
                        background: importFormat === format ? "var(--color-text-primary)" : "var(--color-bg-elevated)",
                        color: importFormat === format ? "var(--color-bg-primary)" : "var(--color-text-secondary)",
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      {format === "json" ? "JSON" : "Markdown"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Input */}
              <div>
                <label style={{ fontSize: 12, color: "var(--color-text-muted)", display: "block", marginBottom: 6, fontWeight: 500 }}>
                  {importFormat === "json" ? "Paste JSON or upload a file" : "Paste Markdown skill or upload a file"}
                </label>
                <textarea
                  value={importText}
                  onChange={(e) => { setImportText(e.target.value); setImportResult(null); setImportError(""); setImportPreview(null); }}
                  placeholder={importFormat === "json"
                    ? `Paste skill JSON here, e.g.:\n[\n  {\n    "name": "my_skill",\n    "description": "What this skill does",\n    "instruction": "Step-by-step instructions..."\n  }\n]`
                    : `Paste Markdown skill here, e.g.:\n---\nname: my_skill\ndescription: What this skill does\n---\n\n# My Skill\n\n## Instruction\nStep-by-step instructions...`}
                  rows={8}
                  style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12, lineHeight: 1.5 }}
                />
              </div>

              {/* File upload */}
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <button onClick={() => fileInputRef.current?.click()} style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 12px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 6, fontSize: 12, color: "var(--color-text-secondary)", cursor: "pointer" }}>
                  <FileJson size={13} /> Choose File
                </button>
                <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>Supports `.json`, `.md`, `.markdown`, `.txt`</span>
                <input ref={fileInputRef} type="file" accept=".json,.md,.markdown,.txt" onChange={handleFileUpload} style={{ display: "none" }} />
              </div>

              {/* Overwrite toggle */}
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--color-text-secondary)", cursor: "pointer" }}>
                <input type="checkbox" checked={importOverwrite} onChange={(e) => setImportOverwrite(e.target.checked)} style={{ accentColor: "var(--color-info)" }} />
                Overwrite existing skills with the same name
              </label>

              {/* Preview button */}
              {!importPreview && !importResult && (
                <button onClick={handleImportPreview} disabled={!importText.trim()} style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "8px 16px", background: "var(--color-info)", color: "white", border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", opacity: !importText.trim() ? 0.5 : 1 }}>
                  Preview Skills
                </button>
              )}

              {/* Error */}
              {importError && (
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "8px 12px", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: 8, fontSize: 12, color: "var(--color-error)" }}>
                  <AlertCircle size={14} style={{ flexShrink: 0, marginTop: 1 }} /> {importError}
                </div>
              )}

              {/* Preview list */}
              {importPreview && !importResult && (
                <div style={{ background: "var(--color-bg-secondary)", borderRadius: 8, padding: 12, border: "1px solid var(--color-border-default)" }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", marginBottom: 8 }}>
                    {importPreview.length} skill(s) will be imported:
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 200, overflowY: "auto" }}>
                    {importPreview.map((s, i) => (
                      <div key={i} style={{ background: "var(--color-bg-card)", borderRadius: 6, padding: "8px 10px", border: "1px solid var(--color-border-default)" }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-primary)" }}>{s.name}</div>
                        <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.description || "(no description)"}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Import result */}
              {importResult && (
                <div style={{ background: "var(--color-bg-secondary)", borderRadius: 8, padding: 12, border: "1px solid var(--color-border-default)" }}>
                  {importResult.imported.length > 0 && (
                    <div style={{ fontSize: 12, color: "var(--color-success)", marginBottom: 6 }}>
                      <CheckCircle2 size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
                      {importResult.imported.length} skill(s) imported: {importResult.imported.map((s) => `${s.name} (${s.action})`).join(", ")}
                    </div>
                  )}
                  {importResult.skipped.length > 0 && (
                    <div style={{ fontSize: 12, color: "var(--color-warning)", marginBottom: 6 }}>
                      {importResult.skipped.length} skill(s) skipped: {importResult.skipped.map((s) => `${s.name} (${s.reason})`).join(", ")}
                    </div>
                  )}
                  {importResult.errors.length > 0 && (
                    <div style={{ fontSize: 12, color: "var(--color-error)" }}>
                      {importResult.errors.length} error(s): {importResult.errors.map((s) => `${s.name}: ${s.error}`).join("; ")}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer buttons */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 12, flexShrink: 0 }}>
              <button onClick={() => setShowImport(false)} style={{ padding: "8px 16px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 8, fontSize: 13, color: "var(--color-text-secondary)", cursor: "pointer" }}>
                {importResult ? "Close" : "Cancel"}
              </button>
              {importPreview && !importResult && (
                <button onClick={handleImportConfirm} disabled={importing} style={{ padding: "8px 16px", background: "var(--color-success)", color: "white", border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", opacity: importing ? 0.6 : 1 }}>
                  {importing ? "Importing..." : `Import ${importPreview.length} Skill(s)`}
                </button>
              )}
            </div>
          </div>
        </>
      )}

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* Search & Filter Bar */}
          <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--color-border-default)", display: "flex", gap: 10, alignItems: "center", background: "var(--color-bg-secondary)" }}>
            <div style={{ flex: 1, position: "relative" }}>
              <Search size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--color-text-muted)" }} />
              <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Search skills..." style={{ ...inputStyle, paddingLeft: 34, fontSize: 13, height: 34 }} />
            </div>
            <div style={{ display: "flex", gap: 4 }}>
              {(["all", "active", "inactive"] as const).map((f) => (
                <button key={f} onClick={() => setFilterStatus(f)} style={{
                  padding: "6px 12px", borderRadius: 6, fontSize: 12, cursor: "pointer", border: "none",
                  background: filterStatus === f ? "var(--color-text-primary)" : "transparent",
                  color: filterStatus === f ? "var(--color-bg-primary)" : "var(--color-text-muted)",
                  fontWeight: filterStatus === f ? 600 : 400, textTransform: "capitalize",
                }}>{f}</button>
              ))}
            </div>
          </div>

          {/* Stats Summary */}
          <div style={{ padding: "12px 20px", display: "flex", gap: 16, fontSize: 13, color: "var(--color-text-muted)", borderBottom: "1px solid var(--color-border-default)", background: "var(--color-bg-secondary)" }}>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Hash size={12} /> {skills.length} total</span>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}><Zap size={12} color="var(--color-success)" /> {activeCount} active</span>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}><CheckCircle2 size={12} color="var(--color-success)" /> {totalSuccess} success</span>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}><XCircle size={12} color="var(--color-error)" /> {totalFail} failed</span>
          </div>

          {/* Skills Grid */}
          <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>
            {loading ? (
              <div style={{ textAlign: "center", padding: 40, color: "var(--color-text-muted)", fontSize: 14 }}>Loading...</div>
            ) : filtered.length === 0 ? (
              <div style={{ textAlign: "center", padding: "80px 20px" }}>
                <div style={{ width: 48, height: 48, borderRadius: 14, background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
                  <Zap size={22} color="var(--color-text-muted)" />
                </div>
                <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>{searchQuery ? "No matching skills" : "No skills yet"}</h3>
                <p style={{ fontSize: 14, color: "var(--color-text-muted)", maxWidth: 380, margin: "0 auto", lineHeight: 1.6 }}>
                  {searchQuery ? "Try a different search term" : "Skills are automatically created when the agent completes complex tasks. You can also create them manually."}
                </p>
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
                {filtered.map((s) => (
                  <div key={s.id} onClick={() => { setSelected(s); setEditing(false); setEditInstruction(s.instruction); setEditDescription(s.description); }} style={{ border: `1px solid ${selected?.id === s.id ? "var(--color-border-hover)" : "var(--color-border-default)"}`, borderRadius: 12, padding: 16, cursor: "pointer", background: "var(--color-bg-card)", opacity: s.is_active ? 1 : 0.5, transition: "opacity 0.2s, border-color 0.2s" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                      <Zap size={14} color={s.is_active ? "var(--color-text-muted)" : "var(--color-error)"} />
                      <span style={{ fontSize: 14, fontWeight: 500, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.name}</span>
                      <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>v{s.version}</span>
                      {!s.is_active && <span style={{ fontSize: 11, color: "var(--color-error)", fontWeight: 500 }}>off</span>}
                    </div>
                    <p style={{ fontSize: 13, color: "var(--color-text-muted)", marginBottom: 12, lineHeight: 1.5, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{s.description}</p>
                    <div style={{ display: "flex", gap: 14, fontSize: 12 }}>
                      <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--color-success)" }}><CheckCircle2 size={13} /> {s.success_count}</span>
                      <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--color-error)" }}><XCircle size={13} /> {s.fail_count}</span>
                      <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--color-text-muted)" }}><TrendingUp size={13} /> {rate(s)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Detail Panel */}
        {selected && (
          <div style={{ width: 400, borderLeft: "1px solid var(--color-border-default)", padding: 20, overflowY: "auto", background: "var(--color-bg-secondary)", flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
              <h2 style={{ fontSize: 16, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{selected.name}</h2>
              <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                <button onClick={() => handleToggle(selected)} title={selected.is_active ? "Disable" : "Enable"} style={{ background: "none", border: "none", color: selected.is_active ? "var(--color-success)" : "var(--color-text-muted)", cursor: "pointer", padding: 4 }}>
                  {selected.is_active ? <ToggleRight size={20} /> : <ToggleLeft size={20} />}
                </button>
                <button onClick={() => { setEditing(!editing); setEditInstruction(selected.instruction); setEditDescription(selected.description); }} title="Edit" style={{ background: "none", border: "none", color: editing ? "var(--color-info)" : "var(--color-text-muted)", cursor: "pointer", padding: 4 }}>
                  <Edit3 size={16} />
                </button>
                {confirmDelete === selected.name ? (
                  <div style={{ display: "flex", gap: 4 }}>
                    <button onClick={() => handleDelete(selected.name)} style={{ padding: "2px 8px", fontSize: 11, background: "var(--color-error)", border: "none", borderRadius: 4, color: "white", cursor: "pointer" }}>Delete</button>
                    <button onClick={() => setConfirmDelete(null)} style={{ padding: "2px 8px", fontSize: 11, background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)", borderRadius: 4, color: "var(--color-text-secondary)", cursor: "pointer" }}>Cancel</button>
                  </div>
                ) : (
                  <button onClick={() => setConfirmDelete(selected.name)} title="Delete" style={{ background: "none", border: "none", color: "var(--color-error)", cursor: "pointer", padding: 4, opacity: 0.6 }}>
                    <Trash2 size={16} />
                  </button>
                )}
                <button onClick={() => { setSelected(null); setEditing(false); setConfirmDelete(null); }} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: 13 }}>Close</button>
              </div>
            </div>

            {/* Status Badge */}
            <div style={{ marginBottom: 20 }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 12px", borderRadius: 20, fontSize: 12, fontWeight: 500, background: selected.is_active ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)", color: selected.is_active ? "var(--color-success)" : "var(--color-error)" }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor" }} />
                {selected.is_active ? "Active" : "Disabled"}
              </span>
            </div>

            <div style={{ marginBottom: 24 }}>
              <h4 style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.8 }}>Description</h4>
              {editing ? (
                <textarea value={editDescription} onChange={(e) => setEditDescription(e.target.value)} rows={3} style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit" }} />
              ) : (
                <p style={{ fontSize: 14, lineHeight: 1.7 }}>{selected.description}</p>
              )}
            </div>

            <div style={{ marginBottom: 24 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <h4 style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: 0.8 }}>Instruction</h4>
                {editing && (
                  <button onClick={handleSaveInstruction} style={{ display: "flex", alignItems: "center", gap: 4, padding: "4px 10px", background: "var(--color-success)", border: "none", borderRadius: 6, fontSize: 12, color: "white", cursor: "pointer" }}>
                    <Save size={12} /> Save
                  </button>
                )}
              </div>
              {editing ? (
                <textarea value={editInstruction} onChange={(e) => setEditInstruction(e.target.value)} rows={10} style={{ ...inputStyle, border: "1px solid var(--color-info)", resize: "vertical", fontFamily: "inherit", lineHeight: 1.7, fontSize: 13 }} />
              ) : (
                <pre style={{ fontSize: 13, color: "var(--color-text-secondary)", background: "var(--color-bg-card)", borderRadius: 10, padding: 14, whiteSpace: "pre-wrap", lineHeight: 1.7, fontFamily: "inherit", border: "1px solid var(--color-border-default)", maxHeight: 300, overflow: "auto" }}>{selected.instruction}</pre>
              )}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 24 }}>
              <div style={{ background: "var(--color-bg-card)", borderRadius: 10, padding: 14, textAlign: "center", border: "1px solid var(--color-border-default)" }}>
                <div style={{ fontSize: 22, fontWeight: 700, color: "var(--color-success)" }}>{selected.success_count}</div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>Success</div>
              </div>
              <div style={{ background: "var(--color-bg-card)", borderRadius: 10, padding: 14, textAlign: "center", border: "1px solid var(--color-border-default)" }}>
                <div style={{ fontSize: 22, fontWeight: 700, color: "var(--color-error)" }}>{selected.fail_count}</div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>Failed</div>
              </div>
              <div style={{ background: "var(--color-bg-card)", borderRadius: 10, padding: 14, textAlign: "center", border: "1px solid var(--color-border-default)" }}>
                <div style={{ fontSize: 22, fontWeight: 700, color: "var(--color-info)" }}>v{selected.version}</div>
                <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>Version</div>
              </div>
            </div>

            {/* Success Rate Bar */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Success Rate</span>
                <span style={{ fontSize: 12, fontWeight: 600 }}>{rate(selected)}%</span>
              </div>
              <div style={{ height: 6, background: "var(--color-bg-elevated)", borderRadius: 3, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${rate(selected)}%`, background: rate(selected) >= 80 ? "var(--color-success)" : rate(selected) >= 50 ? "var(--color-warning)" : "var(--color-error)", borderRadius: 3, transition: "width 0.3s" }} />
              </div>
            </div>

            <div style={{ fontSize: 12, color: "var(--color-text-muted)", display: "flex", flexDirection: "column", gap: 4 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}><Clock size={11} /> Created: {formatDate(selected.created_at)}</div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}><Clock size={11} /> Updated: {formatDate(selected.updated_at)}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
