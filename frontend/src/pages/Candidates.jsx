import { useState, useEffect } from 'react';
import { getAllCandidates } from '../utils/api';
import Header from '../components/Header';

const ProfileModal = ({ isOpen, onClose, candidate }) => {
  if (!isOpen || !candidate) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-3xl overflow-hidden shadow-2xl animate-scale-up">
        <div className="flex items-center justify-between px-8 py-6 border-b border-slate-800 bg-slate-900/50">
          <div>
            <h2 className="text-2xl font-bold text-white">{candidate.name}</h2>
            <p className="text-sm font-medium text-slate-400 mt-1">{candidate.job || 'Role unknown'}</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-slate-800 text-slate-400 hover:text-white transition-colors">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          </button>
        </div>
        
        <div className="p-8 space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-slate-800/50 rounded-2xl p-5 border border-slate-700/50">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">Score</p>
              <div className="flex items-end gap-3">
                <span className="text-3xl font-display font-bold text-white">{candidate.score || 0}</span>
              </div>
            </div>
            
            <div className="bg-slate-800/50 rounded-2xl p-5 border border-slate-700/50">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">Experience</p>
              <div className="flex items-end gap-3">
                <span className="text-3xl font-display font-bold text-white">{candidate.exp || '-'}</span>
              </div>
            </div>
          </div>
          
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-3">Skills</h3>
            <div className="flex flex-wrap gap-2">
              {candidate.skills ? (
                candidate.skills.split(',').map((skill, idx) => (
                  <span key={idx} className="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-sm font-medium text-slate-300">
                    {skill.trim()}
                  </span>
                ))
              ) : (
                <p className="text-sm text-slate-500">No skills listed</p>
              )}
            </div>
          </div>
          
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-3">Contact Details</h3>
            <div className="space-y-2">
              <p className="text-sm text-slate-300 flex items-center gap-2">
                <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                {candidate.email || 'Email not provided'}
              </p>
              <p className="text-sm text-slate-300 flex items-center gap-2">
                <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                {candidate.phone || 'Phone not provided'}
              </p>
              <p className="text-sm text-slate-300 flex items-center gap-2">
                <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                {candidate.location && candidate.location !== '-' ? candidate.location : 'Location not provided'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default function Candidates() {
  const [search, setSearch] = useState('');
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  useEffect(() => {
    const fetchCandidates = async () => {
      try {
        const data = await getAllCandidates();
        const enrichedData = data.map(c => ({
          ...c,
          searchStr: `${c.name} ${c.job || ''} ${c.skills || ''}`.toLowerCase()
        }));
        setCandidates(enrichedData);
      } catch (err) {
        console.error('Failed to fetch candidates', err);
      } finally {
        setLoading(false);
      }
    };
    fetchCandidates();
  }, []);

  const filtered = candidates.filter(c => {
    return c.searchStr.includes(search.toLowerCase());
  });
  
  const handleCopyMeetingLink = (candidateId) => {
    // Generate a dummy Teams link
    const dummyTeamsLink = `https://teams.microsoft.com/l/meetup-join/19%3ameeting_Dummy12345%40thread.v2/0?context=%7b%22Tid%22%3a%22dummy-tenant%22%2c%22Oid%22%3a%22dummy-org%22%7d`;
    
    // Copy to clipboard
    navigator.clipboard.writeText(dummyTeamsLink);
    
    // Show visual feedback
    setCopiedId(candidateId);
    setTimeout(() => setCopiedId(null), 2000);
    
    // Open Teams link in a new tab
    window.open(dummyTeamsLink, '_blank');
  };

  return (
    <div className="relative min-h-screen w-full overflow-hidden antialiased pb-20">
      <div className="glow-bg top-[-30%] left-[-20%] animate-pulse-slow"></div>
      <div
        className="glow-bg bottom-[-20%] right-[-10%] animate-pulse-slow"
        style={{ animationDelay: '2s', background: 'radial-gradient(circle, rgba(20,184,166,0.1) 0%, rgba(59,130,246,0.05) 40%, rgba(2,6,23,0) 70%)' }}
      ></div>

      <Header />
      
      <ProfileModal 
        isOpen={!!selectedCandidate} 
        onClose={() => setSelectedCandidate(null)} 
        candidate={selectedCandidate} 
      />

      <main className="relative z-10">
        <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
          <div className="mb-10 flex flex-col gap-2 animate-slide-up opacity-0-init animate-delay-100">
            <div className="mb-2 inline-flex items-center gap-2.5 rounded-full bg-slate-800/80 px-3 py-1.5 ring-1 ring-slate-700 w-max">
              <span className="size-2 rounded-full bg-accent shadow-[0_0_10px_rgba(20,184,166,0.8)]"></span>
              <p className="text-xs font-bold uppercase tracking-[0.15em] text-slate-300">Ready for Interview</p>
            </div>
            <h1 className="font-display text-4xl font-bold tracking-tight sm:text-5xl text-white">Interested Candidates</h1>
            <p className="text-base text-slate-400">Review candidates who have accepted your outreach invitation.</p>
          </div>

          <div className="mb-8 flex flex-wrap items-center gap-4 animate-slide-up opacity-0-init animate-delay-200">
            <div className="glass-dark glass-dark-card rounded-2xl p-6 flex-1 relative overflow-hidden group min-w-[200px]">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-400 relative z-10">Total Interested</p>
              <p className="mt-2 font-display text-4xl font-bold text-white relative z-10">{candidates.length}</p>
              <p className="mt-2 text-[11px] font-semibold text-slate-400 relative z-10">Waiting for next steps</p>
            </div>
            
            <div className="relative flex-[2] min-w-[300px] self-end">
              <svg className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
              <input
                className="input-dark w-full rounded-xl pl-10 pr-4 py-4 text-sm placeholder:text-slate-500"
                placeholder="Search candidates by name or skill..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>

          <div className="glass-dark rounded-[24px] overflow-hidden animate-slide-up opacity-0-init animate-delay-300">
            <div className="overflow-x-auto pb-2">
              <table className="w-full min-w-[800px] text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-700 bg-slate-900/50 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                    <th className="py-4 pl-6">Candidate</th>
                    <th className="py-4">Job / Role</th>
                    <th className="py-4">Status</th>
                    <th className="py-4 pr-6 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {loading ? (
                    <tr>
                      <td colSpan="4" className="py-12 text-center text-slate-500">Loading interested candidates...</td>
                    </tr>
                  ) : filtered.length === 0 ? (
                    <tr>
                      <td colSpan="4" className="py-12 text-center text-slate-500">
                        {search ? "No candidates found matching your search." : "No candidates have accepted outreach invites yet."}
                      </td>
                    </tr>
                  ) : (
                    filtered.map(c => (
                      <tr key={c.id} className="table-row-hover border-b border-slate-800/50 group">
                        <td className="py-5 pl-6">
                          <p className="font-bold text-white text-base">{c.name}</p>
                          {c.email && <p className="text-xs text-slate-400 mt-1">{c.email}</p>}
                        </td>
                        <td className="py-5">
                          <p className="font-medium text-slate-300">{c.job || 'Role unknown'}</p>
                          <p className="mt-1 text-[11px] text-slate-500 line-clamp-1 max-w-[200px]">
                            {c.skills ? c.skills : ''}
                          </p>
                        </td>
                        <td className="py-5">
                          <span className="inline-flex rounded-full bg-accent/20 px-3 py-1 text-[11px] font-bold text-accent ring-1 ring-accent/30 shadow-[0_0_8px_rgba(20,184,166,0.15)] flex items-center gap-1.5 w-max">
                            <span className="size-1.5 rounded-full bg-accent animate-pulse"></span>
                            Interested
                          </span>
                        </td>
                        <td className="py-5 pr-6">
                          <div className="flex items-center justify-end gap-3">
                            <button 
                              onClick={() => setSelectedCandidate(c)}
                              className="rounded-xl bg-slate-800 px-4 py-2 text-xs font-bold text-white ring-1 ring-slate-700 hover:bg-slate-700 transition-all flex items-center gap-2"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
                              View Profile
                            </button>
                            <button 
                              onClick={() => handleCopyMeetingLink(c.id)}
                              className="btn-neon rounded-xl px-4 py-2 text-xs font-bold text-white flex items-center gap-2"
                            >
                              {copiedId === c.id ? (
                                <>
                                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                                  Copied!
                                </>
                              ) : (
                                <>
                                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path></svg>
                                  Copy meeting link
                                </>
                              )}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
