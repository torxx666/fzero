import { Mic, Square, Loader2, Edit3, CheckCircle2 } from 'lucide-react';
import { useRecorder } from './hooks/useRecorder';
import { useState, useRef, useEffect } from 'react';

function App() {
    const [isUploading, setIsUploading] = useState(false);
    const [transcript, setTranscript] = useState<string>("");
    const [isValidated, setIsValidated] = useState(false);
    const transcriptRef = useRef<HTMLTextAreaElement>(null);

    // Auto-scroll transcript when new text is added (only if not validated)
    useEffect(() => {
        if (transcriptRef.current && !isValidated) {
            transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
        }
    }, [transcript, isValidated]);

    const handleTranscribeBlob = async (blob: Blob) => {
        setIsUploading(true);
        const formData = new FormData();
        formData.append('file', blob, 'chunk.webm');

        try {
            const response = await fetch('/api/transcribe', {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            if (data.transcript && data.transcript.trim()) {
                setTranscript(prev => {
                    const newText = data.transcript.trim();
                    return prev ? prev + ' ' + newText : newText;
                });
            }
        } catch (error) {
            console.error('Transcription failed:', error);
        } finally {
            setIsUploading(false);
        }
    };

    const { isRecording, startRecording, stopRecording } = useRecorder(handleTranscribeBlob);

    const toggleRecording = () => {
        if (isRecording) {
            stopRecording();
        } else {
            setTranscript("");
            setIsValidated(false);
            startRecording();
        }
    };

    const [isSynthesizing, setIsSynthesizing] = useState(false);

    const handleValidation = async () => {
        if (!transcript.trim()) return;

        setIsSynthesizing(true);
        setIsValidated(true);

        try {
            const response = await fetch('/api/synthesize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: transcript }),
            });

            if (!response.ok) throw new Error("Synthesis failed");

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.play();
        } catch (error) {
            console.error('Synthesis failed:', error);
            setIsValidated(false);
        } finally {
            setIsSynthesizing(false);
        }
    };

    return (
        <div className="flex flex-col items-center justify-center min-h-screen p-6 text-slate-100">
            <div className="w-full max-w-2xl p-8 rounded-3xl glass space-y-8 shadow-2xl transition-all duration-500 border border-white/10 bg-white/5 backdrop-blur-2xl">
                <header className="text-center space-y-2">
                    <h1 className="text-4xl font-black bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-500 bg-clip-text text-transparent italic tracking-tight">
                        VOICE AI STUDIO
                    </h1>
                    <p className="text-slate-400 text-xs font-medium uppercase tracking-[0.2em]">Flux en direct • Correction manuelle</p>
                </header>

                <main className="flex flex-col items-center gap-10">
                    <div className="flex flex-col items-center gap-4">
                        <button
                            onClick={toggleRecording}
                            className={`w-28 h-28 rounded-full flex items-center justify-center transition-all duration-500 transform active:scale-95 ${isRecording
                                ? 'bg-red-500 shadow-[0_0_50px_-10px_rgba(239,68,68,0.5)] record-pulse'
                                : 'bg-indigo-600 hover:bg-indigo-500 shadow-[0_0_50px_-10px_rgba(79,70,229,0.4)]'
                                }`}
                        >
                            {isRecording ? <Square size={36} fill="white" stroke="none" /> : <Mic size={40} />}
                        </button>
                        <div className="h-6">
                            {isRecording && (
                                <div className="flex items-center gap-2">
                                    <span className="flex h-2 w-2 rounded-full bg-red-500 animate-ping"></span>
                                    <span className="text-red-500 text-[10px] font-black uppercase tracking-[0.3em]">Enregistrement Live</span>
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="w-full space-y-6">
                        <div className={`group relative rounded-2xl transition-all duration-300 border ${isRecording
                            ? 'bg-indigo-500/5 border-indigo-500/30 ring-1 ring-indigo-500/20'
                            : 'bg-black/40 border-white/10'
                            } ${isValidated ? 'border-emerald-500/50 ring-1 ring-emerald-500/20' : ''}`}>

                            <div className="flex items-center justify-between px-5 py-3 border-b border-white/5 bg-white/5">
                                <div className="flex items-center gap-2 text-[10px] font-bold text-indigo-400 uppercase tracking-widest">
                                    <Edit3 size={12} />
                                    <span>Transcription</span>
                                    {isUploading && <Loader2 className="w-3 h-3 animate-spin" />}
                                </div>
                                <div className="text-[10px] text-slate-500 font-mono">
                                    {transcript.length} chars
                                </div>
                            </div>

                            <textarea
                                ref={transcriptRef}
                                value={transcript}
                                onChange={(e) => setTranscript(e.target.value)}
                                placeholder={isRecording ? "L'IA écoute vos mots..." : "Cliquez sur le micro pour commencer."}
                                className="w-full min-h-[250px] p-6 bg-transparent text-slate-200 text-lg leading-relaxed outline-none resize-none transition-all placeholder:text-slate-600"
                            />
                        </div>

                        <div className="flex justify-center pt-2">
                            <button
                                onClick={handleValidation}
                                disabled={!transcript.trim() || isRecording || isValidated || isSynthesizing}
                                className={`px-10 py-4 rounded-2xl font-bold flex items-center gap-3 transition-all duration-300 ${!transcript.trim() || isRecording || isValidated || isSynthesizing
                                        ? 'bg-white/5 text-slate-600 cursor-not-allowed opacity-50'
                                        : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-xl shadow-emerald-600/20 hover:-translate-y-1'
                                    }`}
                            >
                                {isSynthesizing ? (
                                    <><Loader2 className="animate-spin" /> Génération de la voix...</>
                                ) : isValidated ? (
                                    <><CheckCircle2 className="text-emerald-300" /> Texte Validé</>
                                ) : (
                                    'Valider le texte'
                                )}
                            </button>
                        </div>
                    </div>
                </main>

                <footer className="pt-6 border-t border-white/5 flex justify-between items-center text-[9px] text-slate-500 font-bold uppercase tracking-[0.2em]">
                    <div className="flex items-center gap-4">
                        <span>Whisper Base</span>
                        <span className="w-1 h-1 rounded-full bg-slate-700"></span>
                        <span>French Optimized</span>
                    </div>
                    <span>Mode: Standalone Chunks</span>
                </footer>
            </div>
        </div>
    );
}

export default App;
