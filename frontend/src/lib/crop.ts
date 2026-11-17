// Cuts the square the user framed out of the original photo.

export interface PixelArea {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Longest side of the uploaded crop; the model resizes far below this. */
const MAX_SIDE = 1024;

/** Returns the framed region as a square JPEG, downscaled to at most MAX_SIDE pixels. */
export async function cropToJpeg(src: string, area: PixelArea): Promise<Blob> {
  const image = new Image();
  image.src = src;
  await image.decode();

  const side = Math.min(Math.round(area.width), MAX_SIDE);
  const canvas = document.createElement("canvas");
  canvas.width = side;
  canvas.height = side;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Canvas 2D context is unavailable");
  context.drawImage(image, area.x, area.y, area.width, area.height, 0, 0, side, side);

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("Could not encode the crop"))),
      "image/jpeg",
      0.92,
    );
  });
}
