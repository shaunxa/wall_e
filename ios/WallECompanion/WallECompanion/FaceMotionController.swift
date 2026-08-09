import AVFoundation
import UIKit
import Vision

final class FaceMotionController: NSObject, ObservableObject {
    @Published var enabled = false
    @Published private(set) var status = "Face control off"
    @Published var minimumFaceWidth: CGFloat = 0.20
    @Published var maximumFaceWidth: CGFloat = 0.40
    var onIntent: ((String) -> Void)?

    let session = AVCaptureSession()
    private let cameraQueue = DispatchQueue(label: "WallECompanion.camera")
    private let visionQueue = DispatchQueue(label: "WallECompanion.vision")
    private var configured = false
    private var lastIntent = Date.distantPast
    private var lastIntentName = ""
    private var runtimeErrorObserver: NSObjectProtocol?
    private var videoOutput: AVCaptureVideoDataOutput?
    private var videoOrientation: AVCaptureVideoOrientation = .portrait

    override init() {
        super.init()
        runtimeErrorObserver = NotificationCenter.default.addObserver(
            forName: .AVCaptureSessionRuntimeError,
            object: session,
            queue: .main
        ) { [weak self] notification in
            let error = notification.userInfo?[AVCaptureSessionErrorKey] as? NSError
            self?.status = "Camera unavailable: " + (error?.localizedDescription ?? "restart Face control")
            self?.enabled = false
        }
    }

    deinit {
        if let runtimeErrorObserver {
            NotificationCenter.default.removeObserver(runtimeErrorObserver)
        }
    }

    func setEnabled(_ enabled: Bool) {
        if enabled { start() } else { stop() }
    }

    /// Keeps Vision's image coordinates aligned with the on-screen preview.
    func setInterfaceOrientation(_ interfaceOrientation: UIInterfaceOrientation) {
        guard let videoOrientation = AVCaptureVideoOrientation(interfaceOrientation) else { return }
        cameraQueue.async { [weak self] in
            guard let self else { return }
            self.videoOrientation = videoOrientation
            self.videoOutput?.connection(with: .video)?.videoOrientation = videoOrientation
        }
    }

    private func start() {
        AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
            DispatchQueue.main.async {
                guard let self else { return }
                guard granted else { self.enabled = false; self.status = "Camera permission required"; return }
                self.enabled = true
                self.status = "Starting front camera…"
                self.cameraQueue.async {
                    guard self.configure() else {
                        DispatchQueue.main.async {
                            self.enabled = false
                            self.status = "Front camera is unavailable"
                        }
                        return
                    }
                    if !self.session.isRunning { self.session.startRunning() }
                    DispatchQueue.main.async { self.status = "Find your face" }
                }
            }
        }
    }

    private func stop() {
        enabled = false; lastIntentName = ""; status = "Face control off"
        cameraQueue.async { [session] in if session.isRunning { session.stopRunning() } }
    }

    private func configure() -> Bool {
        if configured { return true }
        session.beginConfiguration(); session.sessionPreset = .medium
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front),
              let input = try? AVCaptureDeviceInput(device: device) else { session.commitConfiguration(); return false }
        let output = AVCaptureVideoDataOutput(); output.alwaysDiscardsLateVideoFrames = true
        output.setSampleBufferDelegate(self, queue: visionQueue)
        guard session.canAddInput(input), session.canAddOutput(output) else { session.commitConfiguration(); return false }
        session.addInput(input); session.addOutput(output)
        if let connection = output.connection(with: .video) {
            connection.videoOrientation = videoOrientation
            connection.automaticallyAdjustsVideoMirroring = false
            connection.isVideoMirrored = true
        }
        session.commitConfiguration(); videoOutput = output; configured = true
        return true
    }

    private func face(centerX: CGFloat?, width: CGFloat?) {
        DispatchQueue.main.async { [weak self] in
            guard let self, self.enabled else { return }
            guard let centerX, let width else {
                self.status = "Find your face"
                self.sendIntent("STOP")
                return
            }

            let intent: String
            
            if width > self.maximumFaceWidth {
                intent = "REV"
                self.status = "Too close → backing up"
            } else if width < self.minimumFaceWidth {
                intent = "FWD"
                self.status = "Too far → move closer"
            } else if centerX < 0.42 {
                intent = "DRIVE_LEFT"
                self.status = "Face left → turning left"
            } else if centerX > 0.58 {
                intent = "DRIVE_RIGHT"
                self.status = "Face right → turning right"
            } else {
                intent = "STOP"
                self.status = "Face centered"
            }
            self.sendIntent(intent)
        }
    }

    private func sendIntent(_ intent: String) {
        let now = Date()
        guard intent != lastIntentName || now.timeIntervalSince(lastIntent) > 0.75 else { return }
        lastIntent = now
        lastIntentName = intent
        onIntent?(intent)
    }
}

extension FaceMotionController: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        let request = VNDetectFaceRectanglesRequest { [weak self] request, _ in
            let faces = request.results as? [VNFaceObservation]
            let largest = faces?.max { $0.boundingBox.width < $1.boundingBox.width }
            self?.face(
                centerX: largest.map { $0.boundingBox.midX },
                width: largest.map { $0.boundingBox.width }
            )
        }
        try? VNImageRequestHandler(cmSampleBuffer: sampleBuffer, orientation: .up, options: [:]).perform([request])
    }
}
