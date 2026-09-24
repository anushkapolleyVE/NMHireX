import { useState, useEffect } from 'react';
import { getOutreachData, updateCandidateStatus } from '../utils/api';
import Header from '../components/Header';

export default function Outreach() {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchOutreach = async () => {
      try {
        const data = await getOutreachData();
        if (data && Array.isArray(data)) {
          setCandidates(data);
        }
      } catch (err) {
        console.error('Failed to fetch outreach data', err);
      } finally {
        setLoading(false);
      }
    };
    fetchOutreach();
  }, []);

  const handleStatusUpdate = async (jobId, candidateId, status) => {
    try {
      await updateCandidateStatus(jobId, candidateId, status);
      // Update local state
      setCandidates(prev => prev.map(c =>
        (c.id === candidateId && c.job_id === jobId) ? { ...c, status } : c
      ));
    } catch (err) {
      console.error('Failed to update status', err);
    }
  };

  return (
    <div className="relative min-h-screen w-full overflow-hidden antialiased pb-20">
      <div className="glow-bg top-[-30%] left-[-20%] animate-pulse-slow"></div>
      <div
        className="glow-bg bottom-[-20%] right-[-10%] animate-pulse-slow"
        style={{ animationDelay: '2s', background: 'radial-gradient(circle, rgba(20,184,166,0.1) 0%, rgba(59,130,246,0.05) 40%, rgba(2,6,23,0) 70%)' }}
      ></div>

      <Header />

      <main className="relative z-10">
        <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
          <div className="mb-10 flex flex-col gap-2 animate-slide-up opacity-0-init animate-delay-100">
            <h1 className="font-display text-4xl font-bold tracking-tight sm:text-5xl text-white">Outreach Responses</h1>
            <p className="text-base text-slate-400">Track and respond to candidates you've reached out to.</p>
          </div>

          <div className="space-y-4 animate-slide-up opacity-0-init animate-delay-200">
            {loading ? (
              <div className="py-12 text-center text-slate-500">Loading outreach candidates...</div>
            ) : candidates.length === 0 ? (
              <div className="glass-dark rounded-2xl p-12 text-center border border-slate-800">
                <p className="text-lg font-bold text-slate-300">No candidates in outreach.</p>
                <p className="text-sm text-slate-500 mt-2">When you send WhatsApp invites or add candidates to outreach, they'll appear here.</p>
              </div>
            ) : (
              candidates.map(candidate => (
                <div key={`${candidate.job_id}-${candidate.id}`} className="glass-dark glass-dark-card rounded-2xl p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
                  <div>
                    <h3 className="text-xl font-bold text-white mb-1">{candidate.name}</h3>
                    <p className="text-sm text-slate-400">{candidate.job}</p>
                    {candidate.replied_message && (
                      <div className="mt-3 bg-slate-800/50 rounded-lg p-3 border border-slate-700/50">
                        <p className="text-xs text-slate-500 mb-1 uppercase tracking-wider font-semibold">Reply</p>
                        <p className="text-sm text-slate-300 italic">"{candidate.replied_message}"</p>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto shrink-0">
                    {candidate.status === 'NOT_INTERESTED' ? (
                      <span className="rounded-xl bg-slate-800/80 px-4 py-2 text-sm font-bold text-slate-500 ring-1 ring-slate-700">Not Interested</span>
                    ) : candidate.status === 'INTERVIEW_LINK_SENT' || candidate.status === 'INTERESTED' ? (
                      <span className="rounded-xl bg-brand/20 px-4 py-2 text-sm font-bold text-brand ring-1 ring-brand/30 flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                        Interview link sent
                      </span>
                    ) : (
                      <>
                        <button
                          onClick={() => handleStatusUpdate(candidate.job_id, candidate.id, 'NOT_INTERESTED')}
                          className="flex-1 sm:flex-none rounded-xl bg-slate-800 hover:bg-slate-700 px-5 py-2.5 text-sm font-bold text-slate-300 transition-colors ring-1 ring-slate-700"
                        >
                          Not Interested
                        </button>
                        <button
                          onClick={() => handleStatusUpdate(candidate.job_id, candidate.id, 'INTERESTED')}
                          className="flex-1 sm:flex-none btn-neon rounded-xl px-5 py-2.5 text-sm font-bold text-white shadow-sm"
                        >
                          Interested
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
