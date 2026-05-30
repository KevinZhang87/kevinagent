"use client";

import { useState, useRef, useEffect, KeyboardEvent, useCallback } from "react";
import { ArrowUp, Paperclip, Image, Mic, X, FileText, Square } from "lucide-react";

export interface AttachedFile {
  file: File;
  id: string;
  preview?: string; // data URL for images
}

interface ChatInputProps {
  onSend: (message: string, files?: AttachedFile[]) => void;
  isLoading: boolean;
}

export function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState<AttachedFile[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Cleanup MediaRecorder on unmount
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = message.trim();
    if ((!trimmed && attachments.length === 0) || isLoading) return;
    onSend(trimmed, attachments.length > 0 ? attachments : undefined);
    setMessage("");
    setAttachments([]);
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }, [message, attachments, isLoading, onSend]);

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 200) + "px"; }
  };

  // File selection
  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    const newAttachments: AttachedFile[] = [];
    Array.from(files).forEach((file) => {
      const att: AttachedFile = { file, id: crypto.randomUUID() };
      if (file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = (ev) => {
          att.preview = ev.target?.result as string;
          setAttachments((prev) => [...prev, att]);
        };
        reader.readAsDataURL(file);
      } else {
        newAttachments.push(att);
      }
    });
    if (newAttachments.length > 0) {
      setAttachments((prev) => [...prev, ...newAttachments]);
    }
    // Reset input so the same file can be selected again
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (imageInputRef.current) imageInputRef.current.value = "";
  }, []);

  const removeAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  }, []);

  // Voice recording
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        const file = new File([blob], `recording_${Date.now()}.webm`, { type: "audio/webm" });
        const att: AttachedFile = { file, id: crypto.randomUUID() };
        setAttachments((prev) => [...prev, att]);
        stream.getTracks().forEach((t) => t.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch {
      alert("Unable to access microphone. Please check permissions.");
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  }, []);

  const canSend = (message.trim() || attachments.length > 0) && !isLoading;

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div style={{ padding: "14px 24px 24px", background: "var(--color-bg-primary)" }}>
      <div style={{ maxWidth: 800, margin: "0 auto" }}>
        <div style={{ background: "var(--color-bg-card)", border: "1px solid var(--color-border-default)", borderRadius: 16, overflow: "hidden", boxShadow: "0 -4px 24px rgba(0,0,0,0.12)" }}>
          {/* Attachment preview area */}
          {attachments.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, padding: "12px 16px 0", borderTop: "none" }}>
              {attachments.map((att) => (
                <div
                  key={att.id}
                  style={{
                    position: "relative",
                    borderRadius: 10,
                    overflow: "hidden",
                    background: "var(--color-bg-elevated)",
                    border: "1px solid var(--color-border-default)",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: att.preview ? 0 : "8px 12px",
                    maxWidth: 180,
                  }}
                >
                  {att.preview ? (
                    <img src={att.preview} alt={att.file.name} style={{ width: 80, height: 60, objectFit: "cover", display: "block" }} />
                  ) : att.file.type.startsWith("audio/") ? (
                    <div style={{ padding: "8px 12px", display: "flex", alignItems: "center", gap: 6 }}>
                      <Mic size={16} color="var(--color-info)" />
                    </div>
                  ) : (
                    <FileText size={16} color="var(--color-text-muted)" style={{ flexShrink: 0 }} />
                  )}
                  <div style={{ flex: 1, minWidth: 0, padding: att.preview ? "4px 8px 4px 0" : 0 }}>
                    <div style={{ fontSize: 12, color: "var(--color-text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {att.file.name}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: 2 }}>
                      {formatFileSize(att.file.size)}
                    </div>
                  </div>
                  <button
                    onClick={() => removeAttachment(att.id)}
                    style={{
                      position: att.preview ? "absolute" : "relative",
                      top: att.preview ? 4 : "auto",
                      right: att.preview ? 4 : "auto",
                      background: "rgba(0,0,0,0.6)",
                      border: "none",
                      borderRadius: "50%",
                      width: 20,
                      height: 20,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      cursor: "pointer",
                      color: "#fff",
                      flexShrink: 0,
                    }}
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Textarea */}
          <textarea
            ref={textareaRef} value={message} onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown} onInput={handleInput}
            placeholder={attachments.length > 0 ? "Add a message (optional)..." : "Send a message..."} rows={1}
            style={{ width: "100%", background: "transparent", color: "var(--color-text-primary)", fontSize: 16, lineHeight: 1.65, border: "none", outline: "none", resize: "none", padding: "14px 56px 14px 20px", minHeight: 56, maxHeight: 200 }}
          />

          {/* Bottom toolbar: action buttons left, send button right */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 12px 10px" }}>
            <div style={{ display: "flex", gap: 2 }}>
              {/* Hidden file inputs */}
              <input ref={fileInputRef} type="file" multiple onChange={handleFileSelect} style={{ display: "none" }} />
              <input ref={imageInputRef} type="file" multiple accept="image/*" onChange={handleFileSelect} style={{ display: "none" }} />

              {/* Attach file */}
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading}
                title="Attach files"
                style={toolbarBtnStyle}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-bg-elevated)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <Paperclip size={15} />
              </button>

              {/* Attach image */}
              <button
                onClick={() => imageInputRef.current?.click()}
                disabled={isLoading}
                title="Attach image"
                style={toolbarBtnStyle}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-bg-elevated)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <Image size={15} />
              </button>

              {/* Voice input */}
              <button
                onClick={isRecording ? stopRecording : startRecording}
                disabled={isLoading}
                title={isRecording ? "Stop recording" : "Voice input"}
                style={{
                  ...toolbarBtnStyle,
                  background: isRecording ? "rgba(239,68,68,0.15)" : "transparent",
                  color: isRecording ? "var(--color-error)" : "var(--color-text-muted)",
                }}
              >
                {isRecording ? <Square size={13} fill="currentColor" /> : <Mic size={15} />}
                {isRecording && (
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--color-error)", animation: "pulse 1s ease-in-out infinite" }} />
                )}
              </button>
            </div>

            {/* Send button */}
            <button
              onClick={handleSend}
              disabled={!canSend}
              style={{
                width: 36, height: 36, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center",
                border: "none", cursor: canSend ? "pointer" : "default",
                background: canSend ? "var(--color-text-primary)" : "var(--color-bg-elevated)",
                color: canSend ? "var(--color-bg-primary)" : "var(--color-text-muted)",
                transition: "all 0.15s",
              }}
            >
              {isLoading
                ? <div style={{ width: 16, height: 16, border: "2px solid currentColor", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.6s linear infinite" }} />
                : <ArrowUp size={17} strokeWidth={2.5} />}
            </button>
          </div>
        </div>
        <p style={{ fontSize: 13, textAlign: "center", marginTop: 14, color: "var(--color-text-muted)" }}>
          KevinAgent may produce inaccurate information. Verify important results.
        </p>
      </div>
    </div>
  );
}

const toolbarBtnStyle: React.CSSProperties = {
  width: 34,
  height: 34,
  borderRadius: 8,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 4,
  border: "none",
  cursor: "pointer",
  background: "transparent",
  color: "var(--color-text-muted)",
  transition: "background 0.15s",
};
