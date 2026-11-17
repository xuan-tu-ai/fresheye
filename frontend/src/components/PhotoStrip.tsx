import type { ReactNode } from "react";

import type { ImageOut } from "../api/types";

/** Numbered thumbnails of an inspection's photos, three to a row; `children` adds extra slots. */
export function PhotoStrip({ images, children }: { images: ImageOut[]; children?: ReactNode }) {
  return (
    <ul className="grid grid-cols-3 gap-3">
      {images.map((image) => (
        <li
          key={image.seq}
          className="relative aspect-square overflow-hidden rounded-control border-[1.5px] border-navy"
        >
          <img src={image.image_url} alt={`Ảnh ${image.seq}`} className="size-full object-cover" />
          <span className="absolute left-1.5 top-1.5 grid size-6 place-items-center rounded-full bg-navy text-caption font-semibold text-white">
            {image.seq}
          </span>
        </li>
      ))}
      {children}
    </ul>
  );
}
