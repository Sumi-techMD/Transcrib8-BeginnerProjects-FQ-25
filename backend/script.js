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
  const notesStatus = document.getElementById("notes-status");
  const notesOutput = document.getElementById("notes-output");

  // State
  let selectedFile = null;
  let currentTranscript = "";

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

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();

      if (data.transcription) {
        currentTranscript = data.transcription;
        transcriptOutput.textContent = data.transcription;
        statusMessage.textContent = "Transcription complete ✅";
        enableNotes();
      } else if (data.error) {
        statusMessage.textContent = `Error: ${data.error}`;
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
        body: JSON.stringify({ transcript: currentTranscript, format: "markdown" }),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `Status ${response.status}`);

      if (data.notes) {
        notesStatus.textContent = "Notes generated ✅";
        notesOutput.innerHTML = markdownToHtml(data.notes);
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
});
