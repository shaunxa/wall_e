import AVFoundation
import SwiftUI
import UIKit

struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession
    let onInterfaceOrientationChange: (UIInterfaceOrientation) -> Void

    func makeUIView(context: Context) -> PreviewView {
        let view = PreviewView()
        view.previewLayer.session = session
        view.previewLayer.videoGravity = .resizeAspectFill
        if let connection = view.previewLayer.connection {
            connection.automaticallyAdjustsVideoMirroring = false
            connection.isVideoMirrored = true
        }
        view.onInterfaceOrientationChange = onInterfaceOrientationChange
        return view
    }

    func updateUIView(_ uiView: PreviewView, context: Context) {
        uiView.previewLayer.session = session
        uiView.updateVideoOrientation()
    }
}

final class PreviewView: UIView {
    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    var onInterfaceOrientationChange: ((UIInterfaceOrientation) -> Void)?
    private var lastInterfaceOrientation: UIInterfaceOrientation?

    override func didMoveToWindow() {
        super.didMoveToWindow()
        updateVideoOrientation()
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        updateVideoOrientation()
    }

    func updateVideoOrientation() {
        // During a rotation layout pass, windowScene can still report the old
        // orientation. Defer one main-loop turn so the preview and Vision use
        // the orientation that UIKit has finished applying.
        DispatchQueue.main.async { [weak self] in
            self?.applyCurrentVideoOrientation()
        }
    }

    private func applyCurrentVideoOrientation() {
        guard let interfaceOrientation = window?.windowScene?.interfaceOrientation,
              let videoOrientation = AVCaptureVideoOrientation(interfaceOrientation),
              interfaceOrientation != lastInterfaceOrientation else { return }
        previewLayer.connection?.videoOrientation = videoOrientation
        lastInterfaceOrientation = interfaceOrientation
        onInterfaceOrientationChange?(interfaceOrientation)
    }
}

extension AVCaptureVideoOrientation {
    init?(_ interfaceOrientation: UIInterfaceOrientation) {
        switch interfaceOrientation {
        case .portrait: self = .portrait
        case .portraitUpsideDown: self = .portraitUpsideDown
        case .landscapeLeft: self = .landscapeLeft
        case .landscapeRight: self = .landscapeRight
        default: return nil
        }
    }
}
