// frontend/script.js
class WatermarkRemover {
    constructor() {
        this.uploadArea = document.getElementById('uploadArea');
        this.fileInput = document.getElementById('fileInput');
        this.methodSelect = document.getElementById('methodSelect');
        this.modeSelect = document.getElementById('modeSelect');
        this.resultsGrid = document.getElementById('resultsGrid');
        this.progressSection = document.getElementById('processingSection');
        this.progressFill =
