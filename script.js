document.addEventListener("DOMContentLoaded", () => {
    const uploadArea = document.getElementById("uploadArea");
    const fileInput = document.getElementById("fileInput");

    const methodSelect = document.getElementById("methodSelect");
    const modeSelect = document.getElementById("modeSelect");

    const processingSection = document.getElementById("processingSection");
    const progressFill = document.getElementById("progressFill");
    const progressText = document.getElementById("progressText");

    const resultsSection = document.getElementById("resultsSection");
    const resultsGrid = document.getElementById("resultsGrid");

    const batchResults = document.getElementById("batchResults");
    const batchSummary = document.getElementById("batchSummary");

    if (!uploadArea || !fileInput) {
        console.error("Upload elements were not found.");
        return;
    }

    // --------------------------------------------------
    // CLICK -> OPEN FILE PICKER
    // --------------------------------------------------

    uploadArea.addEventListener("click", (event) => {
        // Prevent duplicate triggering when clicking directly
        // on the hidden/visible input.
        if (event.target !== fileInput) {
            fileInput.click();
        }
    });

    // --------------------------------------------------
    // FILE PICKER -> PROCESS FILES
    // --------------------------------------------------

    fileInput.addEventListener("change", async (event) => {
        const files = Array.from(event.target.files || []);

        if (files.length === 0) {
            return;
        }

        await processSelectedFiles(files);

        // Allows selecting the same file again later.
        fileInput.value = "";
    });

    // --------------------------------------------------
    // DRAG OVER
    // --------------------------------------------------

    uploadArea.addEventListener("dragover", (event) => {
        event.preventDefault();
        event.stopPropagation();

        uploadArea.classList.add("dragging");
    });

    // --------------------------------------------------
    // DRAG LEAVE
    // --------------------------------------------------

    uploadArea.addEventListener("dragleave", (event) => {
        event.preventDefault();
        event.stopPropagation();

        uploadArea.classList.remove("dragging");
    });

    // --------------------------------------------------
    // DROP
    // --------------------------------------------------

    uploadArea.addEventListener("drop", async (event) => {
        event.preventDefault();
        event.stopPropagation();

        uploadArea.classList.remove("dragging");

        const files = Array.from(event.dataTransfer.files || []);

        if (files.length === 0) {
            return;
        }

        const validFiles = files.filter(isValidImage);

        if (validFiles.length === 0) {
            showError("Please select PNG, JPG, JPEG, WEBP or GIF images.");
            return;
        }

        await processSelectedFiles(validFiles);
    });

    // --------------------------------------------------
    // VALIDATE IMAGE
    // --------------------------------------------------

    function isValidImage(file) {
        const allowedTypes = [
            "image/png",
            "image/jpeg",
            "image/webp",
            "image/gif"
        ];

        return allowedTypes.includes(file.type);
    }

    // --------------------------------------------------
    // PROCESS SELECTED FILES
    // --------------------------------------------------

    async function processSelectedFiles(files) {
        const validFiles = files.filter(isValidImage);

        if (validFiles.length === 0) {
            showError("No supported image files were selected.");
            return;
        }

        if (validFiles.length === 1) {
            await uploadSingleFile(validFiles[0]);
        } else {
            await uploadBatch(validFiles);
        }
    }

    // --------------------------------------------------
    // SINGLE FILE
    // --------------------------------------------------

    async function uploadSingleFile(file) {
        try {
            showProcessing();

            setProgress(10, "Uploading image...");

            const formData = new FormData();

            // IMPORTANT:
            // Flask expects request.files['file']
            formData.append("file", file);

            const response = await fetch("/api/upload", {
                method: "POST",
                body: formData
            });

            const data = await parseResponse(response);

            setProgress(50, "Detecting watermark...");

            if (!response.ok) {
                throw new Error(data.error || "Upload failed.");
            }

            setProgress(70, "Preparing image...");

            await removeWatermark(
                data.file_id,
                file.name
            );

        } catch (error) {
            console.error(error);
            showError(error.message || "Something went wrong.");
            hideProcessing();
        }
    }

    // --------------------------------------------------
    // REMOVE WATERMARK
    // --------------------------------------------------

    async function removeWatermark(fileId, originalName) {
        const method = methodSelect.value;
        const mode = modeSelect.value;

        setProgress(80, "Removing watermark...");

        const response = await fetch("/api/remove", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                file_id: fileId,
                method: method,
                region: null,
                mode: mode
            })
        });

        const data = await parseResponse(response);

        if (!response.ok) {
            throw new Error(data.error || "Watermark removal failed.");
        }

        setProgress(100, "Complete");

        hideProcessing();

        displayResult({
            originalName,
            downloadUrl: data.download_url
        });
    }

    // --------------------------------------------------
    // BATCH UPLOAD
    // --------------------------------------------------

    async function uploadBatch(files) {
        try {
            showProcessing();

            setProgress(10, `Uploading ${files.length} images...`);

            const formData = new FormData();

            files.forEach(file => {
                formData.append("files", file);
            });

            formData.append(
                "method",
                methodSelect.value
            );

            const response = await fetch("/api/batch", {
                method: "POST",
                body: formData
            });

            const data = await parseResponse(response);

            if (!response.ok) {
                throw new Error(data.error || "Batch upload failed.");
            }

            setProgress(100, "Batch processing complete");

            hideProcessing();

            displayBatchResults(data);

        } catch (error) {
            console.error(error);
            showError(error.message || "Batch processing failed.");
            hideProcessing();
        }
    }

    // --------------------------------------------------
    // DISPLAY SINGLE RESULT
    // --------------------------------------------------

    function displayResult(result) {
        resultsSection.style.display = "block";

        resultsGrid.innerHTML = "";

        const card = document.createElement("div");
        card.className = "result-card";

        card.innerHTML = `
            <div class="result-info">
                <strong>${escapeHtml(result.originalName)}</strong>
                <span>Processing complete</span>
            </div>

            <a
                class="download-button"
                href="${result.downloadUrl}"
                download
            >
                Download Result
            </a>
        `;

        resultsGrid.appendChild(card);
    }

    // --------------------------------------------------
    // DISPLAY BATCH RESULTS
    // --------------------------------------------------

    function displayBatchResults(data) {
        batchResults.style.display = "block";

        batchSummary.innerHTML = `
            <p>
                Total:
                <strong>${data.total}</strong>
            </p>

            <p>
                Successful:
                <strong>${data.successful}</strong>
            </p>
        `;

        resultsSection.style.display = "block";

        resultsGrid.innerHTML = "";

        data.results.forEach(result => {
            const card = document.createElement("div");

            card.className = "result-card";

            if (result.status === "success") {
                card.innerHTML = `
                    <div class="result-info">
                        <strong>${escapeHtml(result.filename)}</strong>
                        <span>Success</span>
                    </div>

                    <a
                        class="download-button"
                        href="${result.download_url}"
                        download
                    >
                        Download
                    </a>
                `;
            } else {
                card.innerHTML = `
                    <div class="result-info">
                        <strong>${escapeHtml(result.filename)}</strong>
                        <span class="error">
                            ${escapeHtml(result.error || "Processing failed")}
                        </span>
                    </div>
                `;
            }

            resultsGrid.appendChild(card);
        });
    }

    // --------------------------------------------------
    // PROGRESS
    // --------------------------------------------------

    function showProcessing() {
        processingSection.style.display = "block";
        setProgress(0, "Starting...");
    }

    function hideProcessing() {
        setTimeout(() => {
            processingSection.style.display = "none";
        }, 500);
    }

    function setProgress(percent, text) {
        progressFill.style.width = `${percent}%`;
        progressText.textContent = text;
    }

    // --------------------------------------------------
    // ERROR
    // --------------------------------------------------

    function showError(message) {
        alert(message);
    }

    // --------------------------------------------------
    // RESPONSE PARSER
    // --------------------------------------------------

    async function parseResponse(response) {
        const contentType = response.headers.get("content-type") || "";

        if (contentType.includes("application/json")) {
            return await response.json();
        }

        const text = await response.text();

        throw new Error(
            text || `Server returned HTTP ${response.status}`
        );
    }

    // --------------------------------------------------
    // HTML ESCAPE
    // --------------------------------------------------

    function escapeHtml(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }
});
