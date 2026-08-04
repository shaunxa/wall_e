import AVFoundation
import Speech

final class SpeechController: NSObject, ObservableObject {
    @Published private(set) var listening = false
    @Published private(set) var transcript = ""
    var onIntent: ((String) -> Void)?

    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private let audioEngine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?

    func toggle() { listening ? stop() : start() }

    func start() {
        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            guard status == .authorized else { return }
            AVAudioSession.sharedInstance().requestRecordPermission { granted in
                guard granted else { return }
                DispatchQueue.main.async { self?.beginRecognition() }
            }
        }
    }

    func stop() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        task?.cancel()
        listening = false
    }

    private func beginRecognition() {
        stop()
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        self.request = request
        let node = audioEngine.inputNode
        let format = node.outputFormat(forBus: 0)
        node.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in request.append(buffer) }
        task = recognizer?.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }
            if let text = result?.bestTranscription.formattedString.lowercased() {
                DispatchQueue.main.async {
                    self.transcript = text
                    self.interpret(text)
                }
            }
            if error != nil || result?.isFinal == true { DispatchQueue.main.async { self.stop() } }
        }
        try? audioEngine.start()
        listening = true
    }

    private func interpret(_ text: String) {
        if text.contains("stop") { onIntent?("STOP") }
        else if text.contains("left") { onIntent?("DRIVE_LEFT") }
        else if text.contains("right") { onIntent?("DRIVE_RIGHT") }
        else if text.contains("back") || text.contains("reverse") { onIntent?("REV") }
    }
}
