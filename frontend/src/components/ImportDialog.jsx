import { useEffect, useRef, useState } from "react";
import { CheckCircle2, FileUp, Upload, X } from "lucide-react";
import { Button } from "./ui/button.jsx";
import { createProject, getProjects, importSpecification } from "../services/api.js";

export default function ImportDialog({ onClose, onImported }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [title, setTitle] = useState("");
  const [projectName, setProjectName] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(null);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    getProjects().then((items) => {
      setProjects(items);
      setProjectId(items[0]?.id || "");
    }).catch((caught) => setError(caught.message))
      .finally(() => setLoadingProjects(false));
  }, []);

  function selectFile(selected) {
    setSuccess(null);
    setError("");
    if (!selected) return;
    const name = selected.name.toLowerCase();
    if (!name.endsWith(".json") && !name.endsWith(".yaml") && !name.endsWith(".yml")) {
      setFile(null);
      setError("Unsupported file type. Choose a JSON or YAML specification.");
      return;
    }
    if (selected.size > 5 * 1024 * 1024) {
      setFile(null);
      setError("The file exceeds the 5 MB upload limit.");
      return;
    }
    setFile(selected);
    setStatus("Ready to import");
  }

  async function handleUpload() {
    if (!file) { setError("Choose an OpenAPI JSON or YAML file first."); return; }
    setUploading(true);
    setError("");
    setStatus("Uploading...");
    try {
      let selectedProjectId = projectId;
      if (!selectedProjectId) {
        const project = await createProject({
          name: projectName.trim() || "Imported APIs",
          description: "Created by OpenAPI import",
        });
        selectedProjectId = project.id;
      }
      const result = await importSpecification(selectedProjectId, file, title);
      setSuccess(result);
      setStatus("Import complete");
      onImported?.(result);
    } catch (caught) {
      setError(caught.message);
      setStatus("Import failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="import-dialog stage-import-dialog" role="dialog" aria-modal="true" aria-labelledby="import-title">
        <div className="import-dialog-heading">
          <div><span className="dialog-icon"><FileUp size={18} /></span><div><p className="dialog-kicker">OPENAPI IMPORT</p><h2 id="import-title">Import API specification</h2></div></div>
          <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose}><X size={16} /></Button>
        </div>
        {success ? (
          <div className="import-success"><CheckCircle2 size={28} /><strong>{success.title}</strong><span>Version {success.version_number} imported with {success.endpoint_count} endpoints.</span><Button onClick={onClose}>View API explorer</Button></div>
        ) : (
          <div className="import-body">
            <label className="field-label">API project<select value={projectId} onChange={(event) => setProjectId(event.target.value)} disabled={loadingProjects}><option value="">Create a new project</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
            {!projectId && <label className="field-label">New project name <small>Optional</small><input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="Imported APIs" /></label>}
            <label className="field-label">Specification title <small>Optional</small><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Use title from the specification" /></label>
            <button type="button" className={`dropzone ${file ? "dropzone-selected" : ""}`} onClick={() => inputRef.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); selectFile(event.dataTransfer.files[0]); }}>
              <input ref={inputRef} type="file" accept=".json,.yaml,.yml,application/json,application/yaml" hidden onChange={(event) => selectFile(event.target.files[0])} />
              <Upload size={22} /><strong>{file ? file.name : "Drop a specification here"}</strong><span>{file ? `${(file.size / 1024).toFixed(1)} KB · ${status}` : "JSON or YAML · maximum 5 MB"}</span>
              {!file && <span className="browse-button">Browse file</span>}
            </button>
            {error && <div className="stage-error" role="alert">{error}</div>}
            <div className="import-actions"><span>{loadingProjects ? "Loading projects..." : status}</span><div><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!file || loadingProjects || uploading} onClick={handleUpload}>{uploading ? "Importing..." : "Import specification"}</Button></div></div>
          </div>
        )}
      </section>
    </div>
  );
}
