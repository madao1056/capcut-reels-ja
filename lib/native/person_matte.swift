// 人物の切り抜きマスク（macOS Vision の VNGeneratePersonSegmentationRequest）。
// usage: person_matte <入力フォルダ(png)> <出力フォルダ> [fast|balanced|accurate]
// 入力の各 png と同名で、白=人物 / 黒=背景 のグレースケール png を書く。動画の連番は sequence handler で前後のコマを安定させる。
import CoreImage
import Foundation
import Vision

let args = CommandLine.arguments
guard args.count >= 3 else {
  FileHandle.standardError.write("usage: person_matte <in_dir> <out_dir> [fast|balanced|accurate]\n".data(using: .utf8)!)
  exit(2)
}
let inDir = URL(fileURLWithPath: args[1])
let outDir = URL(fileURLWithPath: args[2])
let q = args.count > 3 ? args[3] : "balanced"
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
let files = (try FileManager.default.contentsOfDirectory(atPath: inDir.path)).filter { $0.hasSuffix(".png") }.sorted()
let ctx = CIContext()
let gray = CGColorSpaceCreateDeviceGray()
let seq = VNSequenceRequestHandler()
for f in files {
  guard let img = CIImage(contentsOf: inDir.appendingPathComponent(f)) else { continue }
  let req = VNGeneratePersonSegmentationRequest()
  req.qualityLevel = q == "fast" ? .fast : (q == "accurate" ? .accurate : .balanced)
  req.outputPixelFormat = kCVPixelFormatType_OneComponent8
  try seq.perform([req], on: img)
  guard let buf = req.results?.first?.pixelBuffer else { continue }
  var m = CIImage(cvPixelBuffer: buf)
  let sx = img.extent.width / m.extent.width, sy = img.extent.height / m.extent.height
  m = m.transformed(by: CGAffineTransform(scaleX: sx, y: sy))
  try ctx.writePNGRepresentation(of: m, to: outDir.appendingPathComponent(f), format: .L8, colorSpace: gray)
}
