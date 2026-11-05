/** The text of a file the person chose. Uses FileReader so it works in every
 *  browser (and in the test environment, whose File has no text()). */
export function readText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      resolve(typeof reader.result === "string" ? reader.result : "");
    };
    reader.onerror = () => {
      reject(new Error("That file could not be read."));
    };
    reader.readAsText(file);
  });
}
