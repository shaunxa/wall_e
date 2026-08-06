import AVFoundation
import Foundation
import Vision

/// Detects horizontal face motion from the front camera.
/// Face left sends `fwd`; face right sends `rev`.
final class FaceMotionController: NSObject, ObservableObject {
    @Published var isTracking = false
    @Published private(set) var status = "Face control off"

    var onCommand: ((String) -> Void)?

    private let captureSession = AVCaptureSession()
    private let captureQueue = DispatchQueue(label: "PybricksRemote.camera")
    private let visionQueue = DispatchQueue(label: "PybricksRemote.vision")
    private var isConfigured = false
    private var previousCenterX: CGFloat?
    private var lastCommandTime = Date.distantPast

    private let movementThreshold: CGFloat = 0.045
    private let commandCooldown: TimeInterval = 0.75

    var previewSession: AVCaptureSession { captureSession }

    func start() {
        AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
            DispatchQueue.main.async {
                guard let self else { return }
                guard granted else {
                    self.isTracking = false
                    self.status = "Camera permission is required"
                    return
                }
                self.configureAndStart()
            }
        }
    }

    func stop() {
        isTracking = false
        previousCenterX = nil
        status = "Face control off"
        captureQueue.async { [captureSession] in
            if captureSession.isRunning { captureSession.stopRunning() }
        }
    }

    private func configureAndStart() {
        guard !captureSession.isRunning else { return }
        if !isConfigured {
            captureSession.beginConfiguration()
            captureSession.sessionPreset = .medium
            guard let camera = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front),
                  let input = try? AVCaptureDeviceInput(device: camera),
                  captureSession.canAddInput(input) else {
                captureSession.commitConfiguration()
                status = "Front camera unavailable"
                return
            }
            let output = AVCaptureVideoDataOutput()
            output.alwaysDiscardsLateVideoFrames = true
            output.setSampleBufferDelegate(self, queue: visionQueue)
            guard captureSession.canAddOutput(output) else {
                captureSession.commitConfiguration()
                status = "Could not start face control"
                return
            }
            captureSession.addInput(input)
            captureSession.addOutput(output)
            if let connection = output.connection(with: .video) {
                connection.videoOrientation = .portrait
                connection.isVideoMirrored = true
            }
            captureSession.commitConfiguration()
            isConfigured = true
        }

        previousCenterX = nil
        isTracking = true
        status = "Looking for a face…"
        captureQueue.async { [captureSession] in
            if !captureSession.isRunning { captureSession.startRunning() }
        }
    }

    private func handle(faceCenterX: CGFloat?) {
        DispatchQueue.main.async { [weak self] in
            guard let self, self.isTracking else { return }
            guard let faceCenterX else {
                self.previousCenterX = nil
                self.status = "Looking for a face…"
                return
            }
            defer { self.previousCenterX = faceCenterX }
            guard let previousCenterX = self.previousCenterX else {
                self.status = "Face found — move left or right"
                return
            }
            let delta = faceCenterX - previousCenterX
            guard abs(delta) >= self.movementThreshold,
                  Date().timeIntervalSince(self.lastCommandTime) >= self.commandCooldown else { return }
            let command = delta < 0 ? "fwd" : "rev"
            self.lastCommandTime = Date()
            self.status = delta < 0 ? "Face left → Forward" : "Face right → Reverse"
            self.onCommand?(command)
        }
    }
}

extension FaceMotionController: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        let request = VNDetectFaceRectanglesRequest { [weak self] request, _ in
            let face = (request.results as? [VNFaceObservation])?.max { $0.boundingBox.width < $1.boundingBox.width }
            self?.handle(faceCenterX: face.map { $0.boundingBox.midX })
        }
        let handler = VNImageRequestHandler(cmSampleBuffer: sampleBuffer, orientation: .up, options: [:])
        try? handler.perform([request])
    }
}
