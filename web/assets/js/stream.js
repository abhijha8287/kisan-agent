// Reads a server-sent events response from fetch() and calls onEvent(type, data) per event.
// EventSource only supports GET, and consultations are multipart POSTs, so we parse by hand.

export async function readEventStream(response, onEvent) {
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;

    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      dispatch(block, onEvent);
    }
  }
  if (buffer.trim()) dispatch(buffer, onEvent);
}

function dispatch(block, onEvent) {
  let type = "message";
  const data = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) type = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (data.length) onEvent(type, JSON.parse(data.join("\n")));
}
