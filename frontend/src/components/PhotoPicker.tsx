import { useRef } from "react";
import type { ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";

/** The inspection a new photo should join; omitted when starting a fresh inspection. */
interface OpenInspection {
  inspectionId: number;
  imageCount: number;
}

/**
 * Camera and library pickers that hand the chosen photo to the crop screen.
 * Render `inputs` once, then call `openCamera` or `openLibrary` from any button.
 */
export function usePhotoPicker(inspection?: OpenInspection) {
  const navigate = useNavigate();
  const cameraInput = useRef<HTMLInputElement>(null);
  const libraryInput = useRef<HTMLInputElement>(null);

  function handlePhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    const source = event.target.hasAttribute("capture") ? "camera" : "library";
    event.target.value = "";
    if (!file) return;
    navigate("/khoanh-mat-ca", {
      state: { src: URL.createObjectURL(file), source, ...inspection },
    });
  }

  const inputs = (
    <>
      <input
        ref={cameraInput}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={handlePhoto}
      />
      <input ref={libraryInput} type="file" accept="image/*" hidden onChange={handlePhoto} />
    </>
  );

  return {
    inputs,
    openCamera: () => cameraInput.current?.click(),
    openLibrary: () => libraryInput.current?.click(),
  };
}
