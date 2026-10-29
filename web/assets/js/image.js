// Downscales photos before upload. Phone cameras produce 4-12 MB images; the vision model
// does not need that resolution, and rural connections are slow.

const MAX_EDGE = 1280;
const QUALITY = 0.85;

export async function prepareImage(file) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();

  const blob = await new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("Could not process photo"))), "image/jpeg", QUALITY),
  );
  return new File([blob], "photo.jpg", { type: "image/jpeg" });
}
