import { Mic, Square, Loader2, Edit3, CheckCircle2, RotateCcw, Sparkles, User, Play, Save, History, Send, Zap, Cpu, Plus, Trash2 } from 'lucide-react';
import { useRecorder } from './hooks/useRecorder';
import { useState, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import AudioVisualizer from './components/AudioVisualizer';

interface Recording {
    id: string;
    text: string;
    created_at: string;
}

interface VoiceProfile {
    id: string;
    name: string;
}

function App() {
    const [isUploading, setIsUploading] = useState(false);
    const [transcript, setTranscript] = useState<string>("");
    const [isValidated, setIsValidated] = useState(false);
    const [audioUrl, setAudioUrl] = useState<string | null>(null);
    const [isSynthesizing, setIsSynthesizing] = useState(false);
    const [recordings, setRecordings] = useState<Recording[]>([]);
    const [isSaving, setIsSaving] = useState(false);
    const [cudaAvailable, setCudaAvailable] = useState<boolean>(false);
    const [deviceName, setDeviceName] = useState<string>("Checking...");

    // Voice Profiles States
    const [voices, setVoices] = useState<VoiceProfile[]>([]);
    const [selectedVoiceId, setSelectedVoiceId] = useState<string | null>(null);
    const [isSavingVoice, setIsSavingVoice] = useState(false);

    // WebSocket Status : pour recevoir les mises à jour en temps réel durant la synthèse
    const [clientId] = useState(() => uuidv4());
    const [statusMessage, setStatusMessage] = useState("");
    const [wsConnected, setWsConnected] = useState(false);

    // Initialisation de la connexion WebSocket au montage du composant
    useEffect(() => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        // L'URL pointe vers le backend via le proxy Vite (/api)
        const wsUrl = `${protocol}//${host}/api/ws/${clientId}`;

        let ws: WebSocket;
        let reconnectTimeout: any;

        const connect = () => {
            console.log("Connecting to WebSocket...");
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                console.log("WebSocket Connected");
                setWsConnected(true);
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.status) {
                        setStatusMessage(data.status);
                    }
                } catch (e) {
                    console.error("WS Message Error:", e);
                }
            };

            ws.onclose = () => {
                console.log("WebSocket Disconnected. Reconnecting...");
                setWsConnected(false);
                reconnectTimeout = setTimeout(connect, 3000);
            };

            ws.onerror = (err) => {
                console.error("WebSocket Error:", err);
                ws.close();
            };
        };

        connect();

        return () => {
            if (ws) ws.close();
            clearTimeout(reconnectTimeout);
        };
    }, [clientId]);

    const transcriptRef = useRef<HTMLTextAreaElement>(null);

    // Fetch history and system status on mount
    useEffect(() => {
        fetchRecordings();
        fetchVoices();
        checkBackendStatus();
    }, []);

    const checkBackendStatus = async () => {
        try {
            const response = await fetch('/api/');
            if (response.ok) {
                const data = await response.json();
                setCudaAvailable(data.cuda_available);
                setDeviceName(data.device_name);
            }
        } catch (error) {
            console.error('Failed to check backend status:', error);
            setDeviceName("Offline");
        }
    };

    const fetchRecordings = async () => {
        try {
            const response = await fetch('/api/recordings');
            if (response.ok) {
                const data = await response.json();
                setRecordings(data);
            }
        } catch (error) {
            console.error('Failed to fetch history:', error);
        }
    };

    const fetchVoices = async () => {
        try {
            const response = await fetch('/api/voices');
            if (response.ok) {
                const data = await response.json();
                setVoices(data);
            }
        } catch (error) {
            console.error('Failed to fetch voices:', error);
        }
    };

    const handleSaveRecording = async () => {
        if (!transcript.trim()) return;
        setIsSaving(true);
        try {
            const response = await fetch('/api/recordings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: transcript }),
            });
            if (response.ok) {
                await fetchRecordings();
                setTranscript("");
                setIsValidated(false);
            }
        } catch (error) {
            console.error('Save failed:', error);
        } finally {
            setIsSaving(false);
        }
    };

    const handleSaveVoice = async () => {
        const name = prompt("Nom du profil vocal :");
        if (!name) return;

        setIsSavingVoice(true);
        try {
            const response = await fetch('/api/voices', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name }),
            });
            if (response.ok) {
                await fetchVoices();
            } else {
                alert("Erreur : Enregistrez d'abord une voix !");
            }
        } catch (error) {
            console.error('Save voice failed:', error);
        } finally {
            setIsSavingVoice(false);
        }
    };

    const handleDeleteVoice = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm("Supprimer ce profil vocal ?")) return;

        try {
            await fetch(`/api/voices/${id}`, { method: 'DELETE' });
            await fetchVoices();
            if (selectedVoiceId === id) setSelectedVoiceId(null);
        } catch (error) {
            console.error(error);
        }
    }

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
                setTranscript(data.transcript.trim());
            }
        } catch (error) {
            console.error('Transcription failed:', error);
        } finally {
            setIsUploading(false);
        }
    };

    const { isRecording, startRecording, stopRecording, stream } = useRecorder(handleTranscribeBlob);

    const toggleRecording = () => {
        if (isRecording) {
            stopRecording();
        } else {
            setTranscript("");
            setAudioUrl(null);
            setIsValidated(false);
            startRecording();
            // Reset selected voice to null (use current recording) when starting new recording
            setSelectedVoiceId(null);
        }
    };

    /**
     * handleSynthesize : Déclenche la génération de voix (TTS)
     * @param engine : "f5", "xtts" ou "basic"
     */
    const handleSynthesize = async (engine: string = "f5") => {
        if (!transcript) return;
        setIsSynthesizing(true);
        setStatusMessage("Envoi de la requête...");
        try {
            const response = await fetch("/api/synthesize", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: transcript,
                    engine,
                    voice_id: selectedVoiceId,
                    client_id: clientId // On passe l'ID client pour que le backend sache à qui envoyer les logs WS
                }),
            });

            if (!response.ok) {
                const errorBlob = await response.blob();
                const errorText = await errorBlob.text();
                const errorData = JSON.parse(errorText);
                alert("Erreur: " + (errorData.error || "Échec de la synthèse"));
                setStatusMessage("Erreur lors de la synthèse");
                throw new Error("Synthesis failed");
            }

            const blob = await response.blob();
            if (blob.type.includes("audio")) {
                const url = URL.createObjectURL(blob);
                setAudioUrl(url);
                setStatusMessage(""); // Clear status on success
                const audio = new Audio(url);
                audio.play();
            } else {
                const errorData = JSON.parse(await blob.text());
                alert("Erreur: " + (errorData.error || "Échec de la synthèse"));
                setStatusMessage("Erreur lors de la synthèse");
            }
        } catch (err) {
            console.error(err);
            setStatusMessage("Erreur de connexion");
        } finally {
            setIsSynthesizing(false);
        }
    };

    const handleSelectFromHistory = (text: string) => {
        setTranscript(text);
        setIsValidated(false);
    };

    return (
        <div className="flex flex-col min-h-screen bg-[#050510] text-slate-100 font-sans selection:bg-indigo-500/30">
            {/* Header */}
            <header className="px-8 py-6 border-b border-white/5 bg-black/20 backdrop-blur-xl flex justify-between items-center z-50">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                        <Mic size={20} className="text-white" />
                    </div>
                    <div>
                        <h1 className="text-xl font-black bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent italic tracking-tight uppercase">
                            Voice AI Studio
                        </h1>
                        <p className="text-[10px] text-indigo-400/80 font-bold uppercase tracking-[0.2em]">Decoupled Acquisition & Synthesis</p>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    {/* CUDA/CPU Status Badge */}
                    <div className={`flex items-center gap-2 px-4 py-2 rounded-full border text-[10px] font-bold uppercase tracking-widest ${cudaAvailable
                        ? 'bg-green-500/10 border-green-500/20 text-green-400'
                        : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                        }`}>
                        {cudaAvailable ? <Zap size={12} className="fill-current" /> : <Cpu size={12} />}
                        <span>{cudaAvailable ? `GPU ACCEL: ${deviceName}` : `CPU MODE: ${deviceName}`}</span>
                    </div>

                    <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-[10px] font-bold uppercase tracking-widest text-slate-400">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        Server Active
                    </div>
                </div>
            </header>

            <main className="flex-1 flex overflow-hidden p-6 gap-6">
                {/* Left Section: Acquisition */}
                <section className="flex-1 flex flex-col gap-6">
                    <div className="p-8 rounded-3xl glass border border-white/10 flex-1 flex flex-col gap-8 shadow-2xl relative overflow-hidden bg-white/5">
                        <div className="absolute top-0 right-0 p-8 opacity-5">
                            <Mic size={150} />
                        </div>

                        <div className="flex items-center justify-between">
                            <h2 className="text-xs font-black uppercase tracking-[0.3em] text-indigo-400">Acquisition</h2>
                            {isRecording && (
                                <div className="flex items-center gap-2">
                                    <span className="flex h-2 w-2 rounded-full bg-red-500 animate-ping"></span>
                                    <span className="text-red-500 text-[10px] font-black uppercase tracking-[0.3em]">Enregistrement Live</span>
                                </div>
                            )}

                            {/* Save Voice Button */}
                            <button
                                onClick={handleSaveVoice}
                                disabled={isRecording || isSavingVoice}
                                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-indigo-500/20 border border-white/10 hover:border-indigo-500/50 text-[10px] font-bold uppercase text-slate-400 hover:text-indigo-400 transition-all"
                            >
                                {isSavingVoice ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                                Sauvegarder cette Voix
                            </button>
                        </div>

                        <div className="flex-1 flex flex-col items-center justify-center gap-10">
                            <div className="relative flex items-center justify-center w-[300px] h-[300px]">
                                {isRecording && (
                                    <div className="absolute inset-0 z-0">
                                        <AudioVisualizer stream={stream} isRecording={isRecording} />
                                    </div>
                                )}

                                <button
                                    onClick={toggleRecording}
                                    className={`relative z-10 w-36 h-36 rounded-full flex items-center justify-center transition-all duration-500 transform active:scale-95 ${isRecording
                                        ? 'bg-transparent' // Invisible button when recording, user clicks the center of Visualizer
                                        : 'bg-indigo-600 hover:bg-indigo-500 shadow-[0_0_80px_-10px_rgba(79,70,229,0.5)] hover:-translate-y-1'
                                        }`}
                                >
                                    {isRecording ? <Square size={48} className="text-white drop-shadow-md" fill="white" stroke="none" /> : <Mic size={56} />}
                                </button>
                            </div>

                            <div className="text-center space-y-2">
                                <p className="text-slate-400 text-sm font-medium">
                                    {isRecording ? "L'IA écoute vos pensées..." : "Appuyez pour commencer l'enregistrement"}
                                </p>
                                <p className="text-[10px] text-slate-600 uppercase tracking-widest">Whisper Base optimized for French</p>
                            </div>
                        </div>

                        {/* Transcription Box */}
                        <div className={`rounded-2xl border transition-all duration-500 ${transcript ? 'opacity-100 translate-y-0' : 'opacity-30 translate-y-4 pointer-events-none'
                            } ${isRecording ? 'bg-white/5 border-indigo-500/30' : 'bg-black/40 border-white/10'}`}>

                            <div className="flex items-center justify-between px-5 py-3 border-b border-white/5 bg-white/5">
                                <div className="flex items-center gap-2 text-[10px] font-bold text-indigo-400 uppercase tracking-widest">
                                    <Edit3 size={12} />
                                    <span>Transcription Interactive</span>
                                    {isUploading && <Loader2 className="w-3 h-3 animate-spin" />}
                                </div>
                                <button
                                    onClick={handleSaveRecording}
                                    disabled={!transcript || isSaving}
                                    className="flex items-center gap-2 px-3 py-1 rounded-lg bg-indigo-500 hover:bg-indigo-400 text-white text-[10px] font-black uppercase transition-all disabled:opacity-50"
                                >
                                    {isSaving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                                    Sauvegarder
                                </button>
                            </div>

                            <textarea
                                ref={transcriptRef}
                                value={transcript}
                                onChange={(e) => setTranscript(e.target.value)}
                                className="w-full min-h-[180px] p-6 bg-transparent text-slate-200 text-lg leading-relaxed outline-none resize-none transition-all placeholder:text-slate-600"
                            />
                        </div>
                    </div>
                </section>

                {/* Right Section: Studio */}
                <section className="w-[450px] flex flex-col gap-6">
                    {/* Status Message */}
                    {statusMessage && (
                        <div style={{
                            marginTop: '10px',
                            padding: '8px 12px',
                            backgroundColor: 'rgba(255, 255, 255, 0.1)',
                            borderRadius: '8px',
                            fontSize: '14px',
                            color: '#a0aec0',
                            fontStyle: 'italic',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px'
                        }}>
                            <span style={{
                                width: '8px',
                                height: '8px',
                                backgroundColor: '#4299e1',
                                borderRadius: '50%',
                                display: 'inline-block',
                                animation: 'pulse 1.5s infinite'
                            }}></span>
                            {statusMessage}
                        </div>
                    )}

                    {/* Synthesis Controls */}
                    <div className="p-8 rounded-3xl glass border border-white/10 bg-white/5 shadow-xl space-y-6">
                        <div className="flex items-center justify-between">
                            <h2 className="text-xs font-black uppercase tracking-[0.3em] text-pink-400">Studio Vocal</h2>
                            <div className="flex gap-2">
                                {audioUrl && (
                                    <button
                                        onClick={() => new Audio(audioUrl).play()}
                                        className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center text-white hover:bg-white/20 transition-all"
                                    >
                                        <RotateCcw size={14} />
                                    </button>
                                )}
                            </div>
                        </div>

                        {/* Voice Selector Grid */}
                        <div className="space-y-2">
                            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest px-1">Choix de la Voix</p>
                            <div className="grid grid-cols-2 gap-2">
                                <button
                                    onClick={() => setSelectedVoiceId(null)}
                                    className={`p-3 rounded-xl border text-xs font-bold transition-all relative ${selectedVoiceId === null
                                        ? 'bg-pink-500/20 border-pink-500 text-pink-400'
                                        : 'bg-white/5 border-white/5 text-slate-400 hover:bg-white/10'
                                        }`}
                                >
                                    Dernière Captation
                                    {selectedVoiceId === null && <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-pink-500 animate-pulse"></span>}
                                </button>

                                {voices.map(voice => (
                                    <div key={voice.id} className="relative group">
                                        <button
                                            onClick={() => setSelectedVoiceId(voice.id)}
                                            className={`w-full h-full p-3 rounded-xl border text-xs font-bold transition-all ${selectedVoiceId === voice.id
                                                ? 'bg-indigo-500/20 border-indigo-500 text-indigo-400'
                                                : 'bg-white/5 border-white/5 text-slate-400 hover:bg-white/10'
                                                }`}
                                        >
                                            {voice.name}
                                        </button>
                                        <button
                                            onClick={(e) => handleDeleteVoice(voice.id, e)}
                                            className="absolute -top-1 -right-1 p-1 rounded-full bg-red-500 text-white opacity-0 group-hover:opacity-100 transition-all scale-75 hover:scale-100"
                                        >
                                            <Trash2 size={10} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="space-y-4 pt-4 border-t border-white/5">
                            <div className="p-4 rounded-xl bg-black/40 border border-white/5 min-h-[80px] text-sm text-slate-300 italic leading-relaxed">
                                {transcript || "Sélectionnez un texte dans l'historique ou enregistrez-en un nouveau..."}
                            </div>

                            <div className="grid grid-cols-1 gap-3">
                                <button
                                    onClick={() => handleSynthesize(transcript, false, true)}
                                    disabled={!transcript || isSynthesizing}
                                    className="w-full py-4 rounded-2xl bg-pink-600 hover:bg-pink-500 text-white font-bold flex items-center justify-center gap-3 transition-all hover:-translate-y-1 shadow-lg shadow-pink-600/20 disabled:opacity-50"
                                >
                                    {isSynthesizing ? <Loader2 className="animate-spin" /> : <Play size={18} />}
                                    Lecture Instantanée (Fast)
                                </button>

                                <div className="flex gap-3">
                                    <button
                                        onClick={() => handleSynthesize(transcript, false, false)}
                                        disabled={!transcript || isSynthesizing}
                                        className="flex-1 py-4 rounded-2xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 font-bold flex items-center justify-center gap-3 transition-all hover:scale-[1.02] disabled:opacity-50"
                                    >
                                        <User size={16} />
                                        Mode Ma Voix
                                    </button>
                                    <button
                                        onClick={() => handleSynthesize(transcript, true, false, "f5")}
                                        disabled={!transcript || isSynthesizing}
                                        className="flex-1 py-4 rounded-2xl bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 font-bold flex items-center justify-center gap-3 transition-all hover:scale-[1.02] disabled:opacity-50"
                                    >
                                        <Sparkles size={16} />
                                        Mode Pro
                                    </button>
                                </div>

                                <button
                                    onClick={() => handleSynthesize(transcript, false, false, "xtts")}
                                    disabled={!transcript || isSynthesizing}
                                    className="w-full py-4 rounded-2xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold flex items-center justify-center gap-3 transition-all hover:-translate-y-1 shadow-lg shadow-indigo-600/20 disabled:opacity-50"
                                >
                                    {isSynthesizing ? <Loader2 className="animate-spin" /> : <Sparkles size={18} />}
                                    Mode Clone Plus (Coqui)
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* History */}
                    <div className="flex-1 p-8 rounded-3xl glass border border-white/10 bg-white/5 shadow-xl flex flex-col gap-6 overflow-hidden">
                        <div className="flex items-center justify-between">
                            <h2 className="text-xs font-black uppercase tracking-[0.3em] text-slate-500">Base de Données</h2>
                            <History size={14} className="text-slate-600" />
                        </div>

                        <div className="flex-1 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
                            {recordings.length === 0 ? (
                                <div className="h-full flex flex-col items-center justify-center text-slate-600 gap-2 opacity-50">
                                    <History size={32} />
                                    <p className="text-[10px] font-bold uppercase tracking-widest">Aucune donnée</p>
                                </div>
                            ) : (
                                recordings.map((rec) => (
                                    <div
                                        key={rec.id}
                                        onClick={() => handleSelectFromHistory(rec.text)}
                                        className="group p-4 rounded-2xl bg-white/5 border border-white/5 hover:border-indigo-500/50 hover:bg-indigo-500/5 transition-all cursor-pointer relative"
                                    >
                                        <p className="text-sm text-slate-300 line-clamp-2 leading-relaxed group-hover:text-white transition-colors">
                                            {rec.text}
                                        </p>
                                        <div className="mt-2 flex items-center justify-between">
                                            <span className="text-[9px] text-slate-500 font-bold uppercase tracking-tighter">
                                                {new Date(rec.created_at).toLocaleString('fr-FR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' })}
                                            </span>
                                            <Send size={10} className="text-indigo-500 opacity-0 group-hover:opacity-100 transition-all transform translate-x-2 group-hover:translate-x-0" />
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </section>
            </main>
        </div>
    );
}

export default App;
