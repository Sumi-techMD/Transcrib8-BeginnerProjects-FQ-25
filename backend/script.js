// script.js
// Frontend logic for uploading audio/video, transcribing via Groq, then generating AI study notes via OpenAI.
// Uses absolute backend URL so opening index.html directly (file://) still works.

const API_BASE_URL = "http://127.0.0.1:5000";

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const dropzone = document.getElementById("upload-dropzone");
  const uploadButton = document.getElementById("upload-button");
  const fileInput = document.getElementById("file-input");
  const fileInfo = document.getElementById("file-info");
  const transcribeButton = document.getElementById("transcribe-button");
  const statusMessage = document.getElementById("status-message");
  const transcriptOutput = document.getElementById("transcript-output");

  const generateNotesButton = document.getElementById("generate-notes-button");
  const downloadNotesButton = document.getElementById("download-notes-button");
  const notesStatus = document.getElementById("notes-status");
  const notesOutput = document.getElementById("notes-output");
  const mindmapBubbles = document.getElementById("mindmap-bubbles");

  // State
  let selectedFile = null;
  let currentTranscript = "";
  let lastNotesMarkdown = "";
  let lastNotesJson = null;

  // File selection via button
  uploadButton.addEventListener("click", (e) => {
    e.preventDefault();
    fileInput.click();
  });

  fileInput.addEventListener("change", () => {
    if (!fileInput.files || fileInput.files.length === 0) return;
    handleSelectedFile(fileInput.files[0]);
  });

  // Drag & Drop
  ["dragenter", "dragover"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("is-dragover");
    });
  });

  ["dragleave", "dragend"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("is-dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove("is-dragover");

    const files = e.dataTransfer.files;
    if (!files || files.length === 0) return;
    handleSelectedFile(files[0]);
  });

  function handleSelectedFile(file) {
    if (!file.type.startsWith("audio/") && !file.type.startsWith("video/")) {
      fileInfo.textContent = "Please upload an audio or video file.";
      selectedFile = null;
      return;
    }
    selectedFile = file;

    const sizeKB = file.size / 1024;
    const sizeMB = sizeKB / 1024;
    const sizeText = sizeMB >= 1 ? `${sizeMB.toFixed(2)} MB` : `${sizeKB.toFixed(1)} KB`;
    fileInfo.textContent = `Selected: ${file.name} (${sizeText})`;

    // Reset output areas
    statusMessage.textContent = "";
    transcriptOutput.textContent = "";
    currentTranscript = "";
    disableNotes();
  }

  // Transcription
  transcribeButton.addEventListener("click", async () => {
    if (!selectedFile) {
      statusMessage.textContent = "Please upload an audio or video file first.";
      return;
    }

    statusMessage.textContent = "Transcribing... this may take a moment.";
    transcriptOutput.textContent = "";
    disableNotes();

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch(`${API_BASE_URL}/transcribe`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (response.ok && data.transcription) {
        currentTranscript = data.transcription;
        transcriptOutput.textContent = data.transcription;
        statusMessage.textContent = "Transcription complete ✅";
        enableNotes();
      } else if (!response.ok) {
        const details = data && data.details ? `\nDetails: ${data.details}` : "";
        statusMessage.textContent = `Transcription failed (${response.status}). ${data.error || "Please try again."}${details}`;
      } else if (data.error) {
        const details = data && data.details ? `\nDetails: ${data.details}` : "";
        statusMessage.textContent = `Error: ${data.error}${details}`;
      } else {
        statusMessage.textContent = "Transcription finished, but no transcript was returned.";
      }
    } catch (err) {
      console.error("Transcription error:", err);
      statusMessage.textContent = "Something went wrong while transcribing. Please try again.";
    }
  });

  // Notes Generation
  generateNotesButton.addEventListener("click", async () => {
    if (!currentTranscript) {
      notesStatus.textContent = "No transcript available yet.";
      return;
    }
    notesStatus.textContent = "Generating notes...";
    notesOutput.innerHTML = "";
    generateNotesButton.disabled = true;

    try {
      const response = await fetch(`${API_BASE_URL}/generate-notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: currentTranscript, format: "json", title: "Study Notes" }),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `Status ${response.status}`);

      // When format=json, the backend returns structured JSON as a string in data.notes
      if (data.notes) {
        notesStatus.textContent = "Notes generated ✅";
        try {
          const parsed = JSON.parse(data.notes);
          // Render markdown-like sections from parsed fields
          const md = jsonNotesToMarkdown(parsed);
          notesOutput.innerHTML = markdownToHtml(md);
          lastNotesMarkdown = md;
          lastNotesJson = parsed;
          // Render bubbles
            // Render bubbles (fallback to derive from key concepts if missing)
            let bubbles = Array.isArray(parsed.mindmap_bubbles) ? parsed.mindmap_bubbles : [];
            if (!bubbles.length && Array.isArray(parsed.key_concepts)) {
              bubbles = parsed.key_concepts.slice(0, 8).map((kc) => ({
                concept: kc.term || "Concept",
                reason: kc.explanation || "key idea",
                importance: 3,
              }));
            }
            renderMindmapBubbles(bubbles);
          enableDownload();
        } catch (e) {
          // Fallback: show raw notes as markdown
          notesOutput.innerHTML = markdownToHtml(data.notes);
          lastNotesMarkdown = data.notes;
          lastNotesJson = null;
          // Try to extract bubbles from raw markdown content (section 'Mindmap Bubbles')
          const extracted = extractBubblesFromMarkdown(lastNotesMarkdown);
          renderMindmapBubbles(extracted);
          enableDownload();
        }
      } else if (data.error) {
        notesStatus.textContent = `Error: ${data.error}`;
      } else {
        notesStatus.textContent = "Finished, but no notes returned.";
      }
    } catch (err) {
      console.error("Notes error:", err);
      notesStatus.textContent = "Failed to generate notes.";
      notesOutput.innerHTML = `<div class="notes-error">${err.message}</div>`;
    } finally {
      generateNotesButton.disabled = false;
    }
  });

  function enableNotes() {
    generateNotesButton.disabled = false;
    notesStatus.textContent = "You can now generate notes.";
  }

  function disableNotes() {
    generateNotesButton.disabled = true;
    notesStatus.textContent = "";
    notesOutput.innerHTML = "";
    if (mindmapBubbles) mindmapBubbles.innerHTML = "";
    lastNotesMarkdown = "";
    lastNotesJson = null;
    if (downloadNotesButton) downloadNotesButton.disabled = true;
  }

  // Minimal markdown renderer (safe, no external libs)
  function markdownToHtml(md) {
    if (!md) return "";
    const escape = (s) => s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Bold **text**
    md = md.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    const lines = md.split(/\r?\n/);
    let html = "";
    let listOpen = false;

    lines.forEach((raw) => {
      const line = raw.trim();
      if (line.length === 0) {
        if (listOpen) {
          html += "</ul>";
          listOpen = false;
        }
        return;
      }

      // Headings
      if (/^#{1,6}\s/.test(line)) {
        if (listOpen) {
          html += "</ul>";
          listOpen = false;
        }
        const level = line.match(/^#+/)[0].length;
        const text = escape(line.replace(/^#{1,6}\s*/, ""));
        const tag = level <= 3 ? `h${level}` : "h3";
        html += `<${tag}>${text}</${tag}>`;
        return;
      }

      // Lists - lines starting with -, *, or numbered
      if (/^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
        if (!listOpen) {
          html += "<ul>";
          listOpen = true;
        }
        const item = escape(line.replace(/^([-*]|\d+\.)\s+/, ""));
        html += `<li>${item}</li>`;
        return;
      }

      // Paragraph
      if (listOpen) {
        html += "</ul>";
        listOpen = false;
      }
      html += `<p>${escape(line)}</p>`;
    });

    if (listOpen) html += "</ul>";
    return html;
  }

  // Convert structured JSON notes into markdown for our renderer
  function jsonNotesToMarkdown(data) {
    const lines = [];
    if (data.title) lines.push(`# ${data.title}`);
    if (data.summary) {
      lines.push("## Summary");
      lines.push(data.summary);
    }
    if (Array.isArray(data.key_concepts) && data.key_concepts.length) {
      lines.push("## Key Concepts");
      data.key_concepts.forEach((kc) => {
        const term = kc.term || "Concept";
        const exp = kc.explanation || "";
        lines.push(`- ${term} - ${exp}`);
      });
    }
    if (Array.isArray(data.important_details) && data.important_details.length) {
      lines.push("## Important Details");
      data.important_details.forEach((d) => lines.push(`- ${d}`));
    }
    if (Array.isArray(data.study_questions) && data.study_questions.length) {
      lines.push("## Study Questions");
      data.study_questions.forEach((q) => {
        const diff = q.difficulty ? ` (${q.difficulty})` : "";
        lines.push(`- ${q.question || "Question"}${diff}`);
      });
    }
    // Omit the markdown Mindmap Bubbles list because bubbles are rendered visually
    return lines.join("\n");
  }

  function renderMindmapBubbles(bubbles) {
    if (!mindmapBubbles) return;
    mindmapBubbles.innerHTML = "";
    if (!Array.isArray(bubbles) || !bubbles.length) return;
    bubbles
      .slice(0, 12)
      .sort((a, b2) => (b2.importance || 3) - (a.importance || 3))
      .forEach((b) => {
      const el = document.createElement("span");
      el.className = "bubble";
      const concept = (b.concept || "Concept").trim();
      const reason = (b.reason || "").trim();
        const importance = b.importance || 3;
        el.innerHTML = `<strong>${escapeHtml(concept)}</strong>${reason ? ' <span class="reason">— ' + escapeHtml(reason) + '</span>' : ''}`;
        el.title = `Importance: ${importance}/5`;
        el.dataset.importance = importance;
        el.addEventListener("click", () => {
          // Simple interaction: filter notes to show where the concept appears
          highlightConcept(concept);
        });
      mindmapBubbles.appendChild(el);
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Extract bubbles heuristically from a markdown section titled "Mindmap Bubbles"
  function extractBubblesFromMarkdown(md) {
    if (!md) return [];
    const lines = md.split(/\r?\n/);
    const bubbles = [];
    let inSection = false;
    for (const raw of lines) {
      const line = raw.trim();
      if (!inSection) {
        if (/^##\s+Mindmap\s+Bubbles/i.test(line)) {
          inSection = true;
        }
        continue;
      }
      if (/^##\s/.test(line) || /^#\s/.test(line)) break;
      if (/^[-*]\s+/.test(line)) {
        let s = line.replace(/^[-*]\s+/, "");
        // Expect **Concept** — reason
        let concept = null;
        let reason = "";
        const strongStart = s.indexOf("**");
        if (strongStart === 0) {
          const strongEnd = s.indexOf("**", 2);
          if (strongEnd > 2) {
            concept = s.substring(2, strongEnd).trim();
            let after = s.substring(strongEnd + 2).trim();
            if (after.startsWith("—")) after = after.substring(1).trim();
            reason = after;
          }
        }
        if (!concept) {
          const parts = s.split("—");
          concept = (parts[0] || s).trim();
          reason = (parts[1] || "").trim();
        }
        bubbles.push({ concept, reason, importance: 3 });
        if (bubbles.length >= 12) break;
      }
    }
    return bubbles;
  }

  // Enable download button
  function enableDownload() {
    if (!downloadNotesButton) return;
    downloadNotesButton.disabled = false;
  }

  // Download notes as a Markdown file; optionally include JSON at end
  if (downloadNotesButton) {
    downloadNotesButton.addEventListener("click", () => {
      if (!lastNotesMarkdown) return;
      const header = `# Exported Notes\n\n`;
      let content = header + lastNotesMarkdown;
      if (lastNotesJson) {
        content += `\n\n---\n\n<!-- Structured JSON -->\n\n` + JSON.stringify(lastNotesJson, null, 2);
      }
      const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `study_notes_${new Date().toISOString().slice(0,10)}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }

  // Highlight occurrences of a concept in the notes output
  function highlightConcept(concept) {
    if (!notesOutput || !concept) return;
    const nodes = notesOutput.querySelectorAll("p, li");
    nodes.forEach((node) => {
      const html = node.innerHTML;
      const re = new RegExp(`(${escapeRegex(concept)})`, "ig");
      node.innerHTML = html.replace(re, '<mark class="concept-highlight">$1</mark>');
    });
  }

  function escapeRegex(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }
});
