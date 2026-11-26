import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { deflateSync } from 'node:zlib'

const __dirname = dirname(fileURLToPath(import.meta.url))
const iconsDir = resolve(__dirname, '../public/icons')

function crc32(buf) {
  let crc = 0xffffffff
  for (let i = 0; i < buf.length; i += 1) {
    crc ^= buf[i]
    for (let bit = 0; bit < 8; bit += 1) {
      const mask = -(crc & 1)
      crc = (crc >>> 1) ^ (0xedb88320 & mask)
    }
  }
  return (crc ^ 0xffffffff) >>> 0
}

function pngChunk(type, data) {
  const typeBuf = Buffer.from(type, 'ascii')
  const lenBuf = Buffer.alloc(4)
  lenBuf.writeUInt32BE(data.length, 0)
  const crcBuf = Buffer.alloc(4)
  crcBuf.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])), 0)
  return Buffer.concat([lenBuf, typeBuf, data, crcBuf])
}

function makeMedicalCrossPng(size) {
  const rows = []
  const pad = Math.max(2, Math.floor(size * 0.12))
  const arm = Math.max(2, Math.floor(size * 0.24))
  const center = Math.floor(size / 2)

  for (let y = 0; y < size; y += 1) {
    const row = Buffer.alloc(1 + size * 4)
    row[0] = 0
    for (let x = 0; x < size; x += 1) {
      const idx = 1 + x * 4
      const inVert = Math.abs(x - center) < arm / 2 && y >= pad && y < size - pad
      const inHoriz = Math.abs(y - center) < arm / 2 && x >= pad && x < size - pad
      if (inVert || inHoriz) {
        row[idx] = 255
        row[idx + 1] = 255
        row[idx + 2] = 255
        row[idx + 3] = 255
      } else {
        row[idx] = 15
        row[idx + 1] = 118
        row[idx + 2] = 110
        row[idx + 3] = 255
      }
    }
    rows.push(row)
  }

  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(size, 0)
  ihdr.writeUInt32BE(size, 4)
  ihdr[8] = 8
  ihdr[9] = 6
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])
  return Buffer.concat([
    signature,
    pngChunk('IHDR', ihdr),
    pngChunk('IDAT', deflateSync(Buffer.concat(rows))),
    pngChunk('IEND', Buffer.alloc(0)),
  ])
}

mkdirSync(iconsDir, { recursive: true })
for (const size of [16, 48, 128]) {
  writeFileSync(resolve(iconsDir, `icon-${size}.png`), makeMedicalCrossPng(size))
}
console.log('Generated extension PNG icons (16, 48, 128) in public/icons/')
