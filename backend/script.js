// script.js

// Wait until the HTML document is fully loaded before running JS
document.addEventListener("DOMContentLoaded", () => {
  const dropzone = document.getElementById("upload-dropzone");
  const uploadButton = document.getElementById("upload-button");
  const fileInput = document.getElementById("file-input");
  const fileInfo = document.getElementById("file-info");
  const transcribeButton = document.getElementById("transcribe-button");
  const statusMessage = document.getElementById("status-message");
  const transcriptOutput = document.getElementById("transcript-output");

  // We'll store the chosen file here so both upload & drag/drop can use it
  let selectedFile = null;

  // Clicking the "Upload a file" button opens the system file picker
  uploadButton.addEventListener("click", (event) => {
    event.preventDefault();
    fileInput.click(); // Programmatically open the hidden file input
  });

  //  When a file is chosen via the file picker
  fileInput.addEventListener("change", () => {
    const files = fileInput.files;
    if (!files || files.length === 0) return;

    handleSelectedFile(files[0]);
  });

  //  Drag & drop events for the dropzone
  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.add("is-dragover"); // visual feedback
    });
  });

  ["dragleave", "dragend"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.remove("is-dragover");
    });
  });

  // When the file is dropped onto the dropzone
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    event.stopPropagation();
    dropzone.classList.remove("is-dragover");

    const dt = event.dataTransfer;
    const files = dt.files;
    if (!files || files.length === 0) return;

    handleSelectedFile(files[0]);
  });

  // Common handler for the selected file (either from picker or drag/drop)
  function handleSelectedFile(file) {
    // Optional safety: only allow audio/video
    if (!file.type.startsWith("audio/") && !file.type.startsWith("video/")) {
      fileInfo.textContent = "Please upload an audio or video file.";
      selectedFile = null;
      return;
    }

    selectedFile = file;

    // Compute human-readable size (KB or MB)
    const sizeKB = file.size / 1024;
    const sizeMB = sizeKB / 1024;
    const sizeText =
      sizeMB >= 1 ? `${sizeMB.toFixed(2)} MB` : `${sizeKB.toFixed(1)} KB`;

    fileInfo.textContent = `Selected: ${file.name} (${sizeText})`;

    // Clear previous output/status when new file is chosen
    statusMessage.textContent = "";
    transcriptOutput.textContent = "";
  }

  // When user clicks "Transcribe Now"
  transcribeButton.addEventListener("click", async () => {
    if (!selectedFile) {
      statusMessage.textContent = "Please upload an audio or video file first.";
      return;
    }

    statusMessage.textContent = "Transcribing... this may take a moment.";
    transcriptOutput.textContent = "";

    try {
      const formData = new FormData();
      // The key "file" must match what app.py expects in request.files["file"]
      formData.append("file", selectedFile);

      // match your backend route: POST /transcribe
      const response = await fetch("/transcribe", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();

      // backend returns { transcription: "..." }
      if (data.transcription) {
        transcriptOutput.textContent = data.transcription;
        statusMessage.textContent = "Transcription complete ✅";
      } else if (data.error) {
        statusMessage.textContent = "Error: " + data.error;
        transcriptOutput.textContent = "";
      } else {
        statusMessage.textContent =
          "Transcription finished, but no transcript was returned.";
        transcriptOutput.textContent = "";
      }
    } catch (error) {
      console.error("Transcription error:", error);
      statusMessage.textContent =
        "Something went wrong while transcribing. Please try again.";
      transcriptOutput.textContent = "";
    }
  });
});
