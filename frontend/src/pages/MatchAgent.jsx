import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import Header from "../components/Header";

import {
  createJob,
  createJobFromText,
  screenJob,
  updateCandidateStatus,
} from "../utils/api";

const CRITERIA_WEIGHTS = {
  mandatory_skills: 30,
  experience: 25,
  domain: 15,
  preferred_skills: 10,
  education: 5,
  location: 5,
  availability: 5,
  other_requirements: 5
};

const formatModalLabel = (key) => {
  return String(key)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
};

function CompareCandidatesModal({ isOpen, onClose, candidates, baseCandidateId }) {
  const [selectedCandidateId, setSelectedCandidateId] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  if (!isOpen || !baseCandidateId) return null;

  const baseCandidate = candidates.find(c => (c.candidate_id || c.id) === baseCandidateId);
  const selectedCandidate = candidates.find(c => (c.candidate_id || c.id) === selectedCandidateId);

  const filteredCandidates = candidates.filter(c => {
    const id = c.candidate_id || c.id;
    if (id === baseCandidateId) return false;
    if (!searchQuery) return true;
    return c.name?.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const getNormalizedScore = (breakdown, key) => {
    if (!breakdown || breakdown[key] === undefined) return 0;
    if (typeof breakdown[key] === 'object' && breakdown[key] !== null) {
      return breakdown[key].percentage || 0;
    }
    return 0;
  };

  const renderCandidateSummary = (candidate, isSelectable = false) => {
    if (!candidate) return null;
    const score = Number(candidate.score || 0).toFixed(0);
    const classification = candidate.classification?.replace(/_/g, ' ') || 'Good Match';
    
    return (
      <div className="bg-slate-800/40 rounded-xl p-5 border border-slate-700 h-full">
        <h3 className="text-lg font-bold text-white mb-1">{candidate.name || 'Unnamed Candidate'}</h3>
        <p className="text-xs text-slate-400 mb-4 line-clamp-2">
          {candidate.current_role || candidate.job || 'Role unknown'} {candidate.current_company ? `@ ${candidate.current_company}` : ''} • {candidate.location || 'Location unknown'} • {candidate.total_experience_years || candidate.exp || '0 yrs'}
        </p>
        
        <div className="flex items-center gap-3">
          <span className="text-3xl font-display font-bold text-accent">{score}</span>
          <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-1 rounded-full bg-accent/20 text-accent border border-accent/30">
            {classification}
          </span>
        </div>
        
        {isSelectable && (
          <button 
            onClick={() => setSelectedCandidateId('')} 
            className="mt-4 text-xs font-bold text-brand hover:text-brand-light transition-colors"
          >
            Pick someone else
          </button>
        )}
      </div>
    );
  };

  const renderComparisonRow = (key) => {
    const label = formatModalLabel(key);
    const weight = CRITERIA_WEIGHTS[key];
    const baseBreakdown = baseCandidate?.score_breakdown || {};
    const selectedBreakdown = selectedCandidate?.score_breakdown || {};
    const baseNorm = getNormalizedScore(baseBreakdown, key);
    const selectedNorm = getNormalizedScore(selectedBreakdown, key);

    return (
      <div key={key} className="grid grid-cols-[2fr_1fr_1fr] gap-4 py-4 border-b border-slate-700/50 items-center">
        <div className="flex justify-between items-center pr-4">
          <span className="text-sm font-medium text-slate-300">{label}</span>
          <span className="text-xs text-slate-500">{weight}%</span>
        </div>
        
        <div className="flex justify-end items-center gap-2">
          <span className={`text-base font-bold ${baseNorm > selectedNorm ? 'text-accent' : 'text-white'}`}>
            {baseNorm}
          </span>
          {baseNorm > selectedNorm && (
            <svg className="w-4 h-4 text-accent" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clipRule="evenodd" />
            </svg>
          )}
        </div>
        
        <div className="flex justify-end items-center gap-2">
          <span className={`text-base font-bold ${selectedNorm > baseNorm ? 'text-accent' : 'text-white'}`}>
            {selectedNorm}
          </span>
          {selectedNorm > baseNorm && (
            <svg className="w-4 h-4 text-accent" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clipRule="evenodd" />
            </svg>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fade-in">
      <div className="bg-slate-900 border border-slate-700/50 rounded-2xl w-full max-w-4xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] animate-slide-up">
        <div className="p-5 border-b border-slate-800 flex justify-between items-center shrink-0">
          <div>
            <h2 className="text-xl font-bold text-white">Compare candidates</h2>
            <p className="text-xs text-slate-400 mt-1">Both candidates were scored against the same job description.</p>
          </div>
          <button onClick={onClose} className="px-4 py-2 rounded-xl text-xs font-bold bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 border border-slate-700 transition-all">
            Close
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-6 scrollbar-hide">
          <div className="grid grid-cols-2 gap-6 mb-8">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">Comparing</p>
              {renderCandidateSummary(baseCandidate)}
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">Against</p>
              {selectedCandidate ? (
                renderCandidateSummary(selectedCandidate, true)
              ) : (
                <div className="bg-slate-800/20 rounded-xl border border-slate-700/50 h-full flex flex-col p-4">
                  <div className="relative mb-3">
                    <input 
                      type="text" placeholder="Search candidate name..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full bg-slate-900 border border-brand/50 rounded-lg py-2.5 pl-3 pr-4 text-sm text-white focus:outline-none focus:ring-1 focus:ring-brand"
                    />
                  </div>
                  <div className="flex-1 overflow-y-auto max-h-[140px] pr-2 space-y-1 custom-scrollbar">
                    {filteredCandidates.map(c => (
                      <button key={c.candidate_id || c.id} onClick={() => setSelectedCandidateId(c.candidate_id || c.id)} className="w-full flex justify-between items-center p-2 rounded hover:bg-slate-800 transition-colors text-left">
                        <span className="text-sm font-medium text-slate-300">{c.name || 'Unnamed'}</span>
                        <span className="text-xs font-bold text-slate-500">{Number(c.score || 0).toFixed(0)}</span>
                      </button>
                    ))}
                    {filteredCandidates.length === 0 && <p className="text-xs text-slate-500 text-center py-4">No candidates found.</p>}
                  </div>
                </div>
              )}
            </div>
          </div>
          {selectedCandidate && (
            <div className="animate-fade-in">
              <div className="border-t border-slate-800 pt-2 mb-8">
                {Object.keys(CRITERIA_WEIGHTS).map(key => renderComparisonRow(key))}
              </div>
              <div className="grid grid-cols-2 gap-6">
                <div className="bg-slate-800/40 rounded-xl p-4 border border-slate-700/50">
                  <p className="text-xs font-bold text-white mb-2">{baseCandidate?.name}</p>
                  <p className="text-xs text-brand font-medium mb-2">AI Assessment Reasoning</p>
                  <p className="text-xs text-slate-400 leading-relaxed">{baseCandidate?.reasoning || 'No specific reasoning provided by the AI.'}</p>
                </div>
                <div className="bg-slate-800/40 rounded-xl p-4 border border-slate-700/50">
                  <p className="text-xs font-bold text-white mb-2">{selectedCandidate?.name}</p>
                  <p className="text-xs text-brand font-medium mb-2">AI Assessment Reasoning</p>
                  <p className="text-xs text-slate-400 leading-relaxed">{selectedCandidate?.reasoning || 'No specific reasoning provided by the AI.'}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function WhatsappInviteModal({ isOpen, onClose, candidate, onSend }) {
  if (!isOpen || !candidate) return null;

  const roleText = candidate.current_role || candidate.job || '';
  const companyText = candidate.current_company ? `@ ${candidate.current_company}` : '';
  const locationText = candidate.location ? `- ${candidate.location}` : '';
  const subtitleArr = [];
  if (roleText) subtitleArr.push(roleText);
  if (companyText) subtitleArr.push(companyText);
  if (locationText) subtitleArr.push(locationText);
  const subtitleFinal = subtitleArr.join(' ');

  const handleSend = async () => {
    if (candidate.phone) {
      if (onSend) {
        await onSend(candidate);
      }
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-[24px] bg-white p-6 shadow-2xl relative animate-in fade-in zoom-in-95 duration-200">
        <div className="flex gap-4 items-start mb-6">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-green-50 text-green-500">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
          </div>
          <div className="pt-1 text-left">
            <h2 className="text-xl font-bold text-slate-800">Send WhatsApp invite</h2>
            <p className="mt-1 text-sm text-slate-500">Confirm the number before it goes out.</p>
          </div>
        </div>

        <div className="mb-6 rounded-2xl bg-slate-50 p-5 border border-slate-100 text-left">
          <h3 className="text-lg font-bold text-slate-800">{candidate.name || 'Unnamed Candidate'}</h3>
          {subtitleFinal && <p className="mt-1 text-sm font-medium text-slate-500">{subtitleFinal}</p>}
          <p className="mt-4 text-xl font-bold text-slate-800">{candidate.phone || 'No phone number'}</p>
        </div>

        <p className="mb-8 text-sm leading-relaxed text-slate-500 text-left">
          They'll receive a short message asking whether they're interested in the role. You can record their reply on this card afterwards.
        </p>

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded-xl border border-slate-200 bg-white px-5 py-2.5 text-sm font-bold text-slate-700 transition-colors hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSend}
            disabled={!candidate.phone}
            className="rounded-xl bg-green-500 px-5 py-2.5 text-sm font-bold text-white transition-colors hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send invite
          </button>
        </div>
      </div>
    </div>
  );
}

export default function MatchAgent() {

  // ==========================================================
  // JOB STATE
  // ==========================================================

  const [selectedFile, setSelectedFile] = useState(null);
  const [fileName, setFileName] = useState("");

  const [jobTitle, setJobTitle] = useState("");

  const [jdText, setJdText] = useState("");

  const [job, setJob] = useState(null);

  const [requirements, setRequirements] = useState(null);

  const [jobId, setJobId] = useState(null);


  // ==========================================================
  // UI STATE
  // ==========================================================

  const [status, setStatus] = useState("Draft");

  const [isAnalyzing, setIsAnalyzing] =
    useState(false);

  const [isSearching, setIsSearching] =
    useState(false);

  const [searchComplete, setSearchComplete] =
    useState(false);

  const [error, setError] = useState("");

  const [candidates, setCandidates] =
    useState([]);


  // ==========================================================
  // DETAILS / OUTREACH
  // ==========================================================

  const [expandedDetails, setExpandedDetails] =
    useState({});

  const [compareModalOpen, setCompareModalOpen] = useState(false);
  const [compareBaseCandidate, setCompareBaseCandidate] = useState(null);

  const [whatsappModalOpen, setWhatsappModalOpen] = useState(false);
  const [selectedWhatsappCandidate, setSelectedWhatsappCandidate] = useState(null);
  const [whatsappContacted, setWhatsappContacted] = useState({});

  const [contacted, setContacted] =
    useState({});

  const [queueReady, setQueueReady] =
    useState(false);

  const [jdModalOpen, setJdModalOpen] = useState(false);
  const [candidatesModalOpen, setCandidatesModalOpen] = useState(false);


  // ==========================================================
  // FILE CHANGE
  // ==========================================================

  const handleFileChange = (e) => {

    const file = e.target.files?.[0];

    if (!file) {
      return;
    }

    setSelectedFile(file);
    setFileName(file.name);

    setError("");

    // Clear pasted JD if user selected a file
    setJdText("");
  };


  // ==========================================================
  // ANALYZE JD
  // ==========================================================

  const handleAnalyze = async () => {

    setError("");

    setSearchComplete(false);

    setCandidates([]);

    setRequirements(null);

    // --------------------------------------------------------
    // Validate input
    // --------------------------------------------------------

    if (!selectedFile && !jdText.trim()) {

      setError(
        "Please upload a job description or paste the JD text."
      );

      return;
    }


    setIsAnalyzing(true);

    setStatus("Analyzing");


    try {

      let result;


      // ------------------------------------------------------
      // FILE
      // ------------------------------------------------------

      if (selectedFile) {

        result = await createJob(
          selectedFile
        );

      }

      // ------------------------------------------------------
      // TEXT
      // ------------------------------------------------------

      else {

        result = await createJobFromText(
          jdText.trim()
        );

      }


      console.log(
        "Job created:",
        result
      );


      // ------------------------------------------------------
      // Save job
      // ------------------------------------------------------

      setJob(result);

      setJobId(
        result.job_id
      );


      // ------------------------------------------------------
      // Save extracted requirements
      // ------------------------------------------------------

      setRequirements(
        result.requirements || {}
      );


      // ------------------------------------------------------
      // Update title
      // ------------------------------------------------------

      const extractedTitle =
        result.requirements?.job_title ||
        result.title ||
        jobTitle ||
        "Job Description";

      setJobTitle(
        extractedTitle
      );


      setStatus(
        "Criteria ready"
      );

    } catch (err) {

      console.error(
        "JD analysis failed:",
        err
      );

      setStatus("Draft");

      setError(
        err.message ||
        "Failed to analyze the job description."
      );

    } finally {

      setIsAnalyzing(false);

    }
  };


  // ==========================================================
  // SCREEN CANDIDATES
  // ==========================================================

  const handleSearch = async (overrideJobId = null) => {

    setError("");

    const idToUse = overrideJobId || jobId;

    if (!idToUse) {

      setError(
        "Please analyze the job description first."
      );

      return;
    }


    setIsSearching(true);

    setSearchComplete(false);

    setStatus("Screening");


    try {

      const result =
        await screenJob(idToUse);


      console.log(
        "Screening result:",
        result
      );


      // ------------------------------------------------------
      // Backend returns:
      //
      // {
      //   job_id,
      //   candidates_evaluated,
      //   top_10: [...]
      // }
      // ------------------------------------------------------

      const rankedCandidates =
        Array.isArray(result?.top_10)
          ? result.top_10
          : [];


      setCandidates(
        rankedCandidates
      );

      setSearchComplete(true);

      setStatus("Screening");

    } catch (err) {

      console.error(
        "Screening failed:",
        err
      );

      setError(
        err.message ||
        "Failed to screen candidates."
      );

      setStatus(
        "Criteria ready"
      );

    } finally {

      setIsSearching(false);

    }
  };

  

  // ==========================================================
  // DETAILS
  // ==========================================================

  const toggleDetails = (candidateId) => {

    setExpandedDetails(
      (prev) => ({
        ...prev,
        [candidateId]:
          !prev[candidateId],
      })
    );
  };


  // ==========================================================
  // CONTACT
  // ==========================================================

  const handleContact = async (candidateId) => {

    setContacted(
      (prev) => ({
        ...prev,
        [candidateId]: true,
      })
    );
    try {
      if (jobId) {
        await updateCandidateStatus(jobId, candidateId, 'CONTACTED');
      }
    } catch (err) {
      console.error('Failed to mark contacted', err);
    }
  };


  // ==========================================================
  // HELPERS
  // ==========================================================

  const formatExperience = () => {

    if (!requirements) {
      return "Not specified";
    }

    const min =
      requirements.minimum_experience;

    const max =
      requirements.maximum_experience;


    if (
      min !== null &&
      min !== undefined &&
      max !== null &&
      max !== undefined
    ) {

      return `${min}–${max} years`;

    }


    if (
      min !== null &&
      min !== undefined
    ) {

      return `${min}+ years`;

    }


    if (
      max !== null &&
      max !== undefined
    ) {

      return `Up to ${max} years`;

    }


    return "Not specified";
  };


  const formatNoticePeriod = () => {

    const value =
      requirements?.notice_period_days;


    if (
      value === null ||
      value === undefined ||
      value === ""
    ) {

      return "Not specified";
    }


    const number =
      Number(value);


    if (!Number.isNaN(number)) {

      if (number === 0) {
        return "Immediate";
      }

      return `${number} days`;
    }


    return String(value);
  };


  const getDisplayName = (skill) => {

    if (
      skill === null ||
      skill === undefined
    ) {

      return "";
    }


    if (
      typeof skill === "object"
    ) {

      return (
        skill.skill_name ||
        skill.normalized_skill_name ||
        skill.name ||
        skill.skill ||
        ""
      );
    }


    return String(skill);
  };


  const formatList = (value) => {

    if (!Array.isArray(value)) {
      return [];
    }

    return value
      .map(getDisplayName)
      .filter(Boolean);
  };


  const getClassificationLabel = (classification) => {
    if (!classification) return "Match";
    return String(classification)
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  };

  const formatBreakdownLabel = (key) => {
    return String(key)
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  };


  // ==========================================================
  // RENDER
  // ==========================================================

  return (

    <div className="relative min-h-screen w-full overflow-hidden antialiased pb-20">

      {/* Background */}

      <div className="glow-bg-large top-[-30%] left-[-20%] animate-pulse-slow"></div>

      <div
        className="glow-bg-large bottom-[-20%] right-[-10%] animate-pulse-slow"
        style={{
          animationDelay: "2s",
          background:
            "radial-gradient(circle, rgba(20,184,166,0.1) 0%, rgba(59,130,246,0.05) 40%, rgba(2,6,23,0) 70%)",
        }}
      ></div>


      <Header />


      
      <main className="relative z-10">
        
        {candidatesModalOpen ? (
          <div className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
            <button onClick={() => setCandidatesModalOpen(false)} className="mb-6 px-5 py-3 bg-slate-800 rounded-xl font-bold hover:bg-slate-700 transition-colors ring-1 ring-slate-700 text-white flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
              Back to Job Intake
            </button>
            <h2 className="font-display text-3xl font-bold mb-8 text-white">Screened Candidates</h2>
            
            <div className="space-y-4">
              {candidates.map((candidate, index) => {
                    const candidateKey = candidate.candidate_id || candidate.id || index;
                    const score = Number(candidate.score || 0);
                    const breakdown = candidate?.score_breakdown && typeof candidate.score_breakdown === "object"
                      ? candidate.score_breakdown
                      : {};
                    const phone = candidate?.phone ? String(candidate.phone).replace(/[^0-9]/g, "") : "";

                    return (
                      <div key={candidateKey} className="candidate-card glass-dark-card bg-slate-800/40 rounded-2xl p-5 border border-slate-700/50">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                          <div>
                            <div className="flex items-center gap-2.5">
                              <p className="text-base font-bold text-white">{candidate.name || "Unnamed Candidate"}</p>
                              <span className="rounded-full bg-accent/20 px-2.5 py-1 text-[10px] font-bold text-accent ring-1 ring-accent/30">
                                {getClassificationLabel(candidate.classification)}
                              </span>
                            </div>
                            <p className="mt-1.5 text-xs font-medium text-slate-400">{candidate.email || "Email unavailable"}</p>
                          </div>
                          <div className="text-right flex flex-col items-end">
                            <p className="font-display text-4xl font-bold text-accent leading-none">{score.toFixed(1)}</p>
                            <p className="mt-1 text-[10px] font-bold uppercase tracking-widest text-slate-500">Match / 100</p>
                          </div>
                        </div>

                        <div className="mt-4 flex flex-wrap gap-2">
                          <span className="rounded-full bg-brand/20 px-3 py-1 text-[11px] font-bold text-brand">Rank #{candidate.rank || index + 1}</span>
                          {candidate.status && (
                            <span className="rounded-full bg-slate-800 px-3 py-1 text-[11px] font-bold text-slate-400 ring-1 ring-slate-700">{candidate.status}</span>
                          )}
                        </div>

                        {/* SCORE BREAKDOWN — DIRECTLY FROM API RESPONSE */}
                        {Object.keys(breakdown).length > 0 && (
                          <div className="mt-5 rounded-xl bg-slate-900/60 p-4 border border-slate-800">
                            <p className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-300">Score breakdown</p>
                            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                              {Object.entries(breakdown).map(([key, value]) => {
                                const item = value && typeof value === "object" ? value : { score: value };
                                return (
                                  <div key={key} className="rounded-lg bg-slate-800/70 p-3">
                                    <p className="text-[10px] font-bold text-slate-400">{formatBreakdownLabel(key)}</p>
                                    <p className="mt-1 text-sm font-bold text-white">
                                      {item.score ?? 0}
                                      {item.max_score !== undefined && item.max_score !== null ? ` / ${item.max_score}` : ""}
                                    </p>
                                    {item.percentage !== undefined && item.percentage !== null && (
                                      <p className="mt-0.5 text-[10px] font-bold text-accent">{item.percentage}%</p>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        <div className="mt-5 flex items-center justify-end gap-3 border-t border-slate-700/50 pt-4">
                          <button onClick={() => toggleDetails(candidateKey)} className="text-xs font-bold text-slate-400 hover:text-white transition-colors px-2 py-1">
                            {expandedDetails[candidateKey] ? "Hide details ↑" : "View details ↓"}
                          </button>
                          <button 
                            onClick={() => {
                              setCompareBaseCandidate(candidate.candidate_id || candidate.id || candidateKey);
                              setCompareModalOpen(true);
                            }} 
                            className="rounded-xl px-4 py-2 text-xs font-bold transition-all bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 border border-slate-700"
                          >
                            Compare
                          </button>
                          <button onClick={() => handleContact(candidateKey)} disabled={contacted[candidateKey]} className={`rounded-xl px-4 py-2 text-xs font-bold transition-all ${contacted[candidateKey] ? "bg-accent/20 text-accent border border-accent/30" : "bg-brand text-white hover:bg-brand-light shadow-sm"}`}>
                            {contacted[candidateKey] ? "✓ Added to outreach" : "Add to outreach"}
                          </button>
                          <button 
                            type="button" 
                            onClick={() => {
                              setSelectedWhatsappCandidate(candidate);
                              setWhatsappModalOpen(true);
                            }} 
                            disabled={whatsappContacted[candidateKey]}
                            className={`rounded-xl px-4 py-2 text-xs font-bold transition-all ${whatsappContacted[candidateKey] ? "bg-green-500/20 text-green-500 border border-green-500/30" : "bg-green-600 text-white hover:bg-green-500 shadow-sm"}`}
                          >
                            {whatsappContacted[candidateKey] ? "✓ Sent invite" : "WhatsApp"}
                          </button>
                        </div>

                        {expandedDetails[candidateKey] && (
                          <div className="mt-4 rounded-xl bg-slate-900/80 p-4 text-xs leading-relaxed border border-slate-800">
                            <p className="text-slate-300"><strong className="text-white">Candidate:</strong>{" "}{candidate.name || "Unnamed Candidate"}</p>
                            {candidate.email && <p className="mt-2 text-slate-300"><strong className="text-white">Email:</strong>{" "}{candidate.email}</p>}
                            <p className="mt-2 text-slate-300"><strong className="text-white">Screening score:</strong>{" "}{score.toFixed(1)}/100</p>
                            {candidate.classification && <p className="mt-2 text-slate-300"><strong className="text-white">Classification:</strong>{" "}{getClassificationLabel(candidate.classification)}</p>}
                            {candidate.phone && <p className="mt-2 text-slate-300"><strong className="text-white">Phone:</strong>{" "}{candidate.phone}</p>}
                            {candidate.reasoning && <p className="mt-3 text-slate-300"><strong className="text-white">Reasoning:</strong>{" "}{candidate.reasoning}</p>}
                          </div>
                        )}
                      </div>
                    );
                  })}

                </div>
              
            {/* =================================================
                  OUTREACH
              ================================================= */}

              {searchComplete &&
                candidates.length > 0 && (

                  <div className="mt-8 flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-gradient-to-r from-brand/20 to-purple-500/20 p-6 border border-slate-700">

                    <div>

                      <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-brand-soft">
                        Step 4 · Outreach
                      </p>


                      <p className="mt-2 text-sm font-medium text-white">

                        Review the eligible candidates before starting outreach.

                      </p>

                    </div>


                    <button
                      onClick={() =>
                        setQueueReady(true)
                      }
                      className="btn-neon rounded-xl px-5 py-3 text-sm font-bold text-white"
                    >
                      Review outreach queue
                    </button>

                  </div>

                )}



              {queueReady && (

                <p className="mt-4 rounded-xl bg-accent/20 px-4 py-3 text-sm font-bold text-accent border border-accent/30">

                  ✓ Outreach queue is ready for review.

                </p>

              )}

            
          </div>
        ) : (
        <div className="mx-auto max-w-7xl px-5 py-8 sm:px-8">


          {/* =================================================
              PAGE HEADER
          ================================================= */}

          <div className="mb-8 flex flex-wrap items-end justify-between gap-6">

            <div>

              <div className="mb-2 inline-flex items-center gap-2.5 rounded-full bg-slate-800/80 px-3 py-1.5 ring-1 ring-slate-700">

                <span className="size-2 rounded-full bg-brand"></span>

                <p className="text-xs font-bold uppercase tracking-[0.15em] text-slate-300">
                  03 · Match agent
                </p>

              </div>


              <h1 className="mt-2 font-display text-4xl font-bold tracking-tight sm:text-5xl text-white">
                Turn a JD into a shortlist.
              </h1>


              <p className="mt-3 max-w-3xl text-base leading-relaxed text-slate-400">
                Upload a job description, let AI create search criteria, then rank candidates using the screening model.
              </p>

            </div>


            <Link
              to="/dashboard"
              className="rounded-xl bg-slate-800/80 px-5 py-3 text-sm font-bold text-white ring-1 ring-slate-700 hover:bg-slate-700 transition-all"
            >
              ← Back to Dashboard
            </Link>

          </div>



          {/* =================================================
              ERROR
          ================================================= */}

          {error && (

            <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-bold text-red-300">

              {error}

            </div>

          )}



          <div className="grid gap-6 xl:grid-cols-12">


            {/* =================================================
                LEFT SIDE
            ================================================= */}

            <section className="glass-dark rounded-[24px] p-6 sm:p-8 xl:col-span-5 h-fit">

              <div className="mb-6 flex items-center justify-between">

                <div>

                  <p className="text-xs font-bold uppercase tracking-[0.15em] text-slate-400">
                    Step 1 · Job intake
                  </p>

                  <h2 className="mt-1 font-display text-2xl font-bold text-white">
                    Create a search
                  </h2>

                </div>


                <span className="rounded-full bg-accent/20 px-3 py-1.5 text-xs font-bold text-accent ring-1 ring-accent/40">

                  {status}

                </span>

              </div>



              {/* JOB TITLE */}

              <div className="mb-5">

                <label
                  htmlFor="jd-title"
                  className="mb-2 block text-xs font-bold text-slate-300"
                >
                  Job title
                </label>


                <input
                  id="jd-title"
                  value={jobTitle}
                  onChange={(e) =>
                    setJobTitle(
                      e.target.value
                    )
                  }
                  placeholder="Job title"
                  className="input-dark w-full rounded-xl px-4 py-3 text-sm font-medium"
                />

              </div>



              {/* FILE UPLOAD */}

              <div className="dropzone-dark rounded-2xl p-8 text-center cursor-pointer group relative">

                <input
                  id="jd-file"
                  type="file"
                  accept=".pdf,.doc,.docx,.txt"
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  onChange={handleFileChange}
                />


                <div className="mx-auto grid size-12 place-items-center rounded-full bg-slate-800 text-brand shadow-sm ring-1 ring-slate-700">

                  <svg
                    className="w-6 h-6"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                    />
                  </svg>

                </div>


                <p className="mt-4 text-base font-bold text-white">
                  Upload Job Description
                </p>


                <p className="mt-1.5 text-xs font-medium text-slate-400">
                  PDF, DOC, DOCX or TXT · up to 10 MB
                </p>


                {fileName && (

                  <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-brand/20 px-3 py-1 text-xs font-bold text-brand">

                    ✓ {fileName} selected

                  </p>

                )}

              </div>



              {/* OR */}

              <div className="my-6 flex items-center gap-4 text-[11px] font-bold uppercase tracking-wider text-slate-500">

                <span className="h-px flex-1 bg-slate-800"></span>

                OR PASTE JD

                <span className="h-px flex-1 bg-slate-800"></span>

              </div>



              {/* JD TEXT */}

              <textarea
                rows="7"
                value={jdText}
                onChange={(e) => {
                  setJdText(
                    e.target.value
                  );

                  if (
                    e.target.value.trim()
                  ) {
                    setSelectedFile(null);
                    setFileName("");
                  }
                }}
                placeholder="Paste the job description here…"
                className="input-dark w-full resize-none rounded-xl px-4 py-3 text-sm mb-6 placeholder:text-slate-600"
              />



              {/* ANALYZE */}

              <button
                onClick={handleAnalyze}
                disabled={isAnalyzing}
                className="w-full rounded-xl px-4 py-3.5 text-sm font-bold text-white shadow-lg flex items-center justify-center gap-2 transition-colors border bg-slate-800 hover:bg-slate-700 border-slate-700"
              >

                {isAnalyzing ? (

                  <>
                    <svg
                      className="size-4 animate-spin"
                      viewBox="0 0 24 24"
                      fill="none"
                    >
                      <circle
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                        className="opacity-25"
                      />

                      <path
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                        fill="currentColor"
                        className="opacity-75"
                      />
                    </svg>

                    AI is analyzing the JD…

                  </>

                ) : (

                  requirements
                    ? "Re-analyze JD"
                    : "Analyze JD & Create Search Criteria"

                )}

              </button>



              {/* =================================================
                  EXTRACTED CRITERIA (COLLAPSED)
              ================================================= */}

              {requirements && (

                <div className="mt-6 flex flex-col gap-4">

                  <div 
                    onClick={() => setJdModalOpen(true)}
                    className="rounded-2xl bg-blue-950/40 p-4 flex items-center justify-between border border-blue-900/50 cursor-pointer hover:bg-blue-900/40 transition-colors"
                  >
                    <div className="flex gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-500/20 text-blue-400">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                      </div>
                      <div>
                        <p className="text-sm font-bold text-white">JD Parsing Result</p>
                        <p className="text-xs font-medium text-slate-400">Click to view the parsed JD details</p>
                      </div>
                    </div>
                    <span className="flex items-center gap-1 text-xs font-bold text-blue-400">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg> Open
                    </span>
                  </div>
                  <button
                    onClick={() => handleSearch()}
                    disabled={isSearching || !jobId}
                    className="w-full rounded-2xl bg-indigo-600 hover:bg-indigo-500 px-4 py-4 text-sm font-bold text-white shadow-lg flex items-center justify-center gap-2 transition-colors border-none disabled:opacity-50"
                  >
                    {isSearching ? (
                      <>
                        <svg className="size-5 animate-spin" viewBox="0 0 24 24" fill="none">
                          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
                          <path d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" fill="currentColor" className="opacity-75" />
                        </svg>
                        Screening candidates…
                      </>
                    ) : (
                      <>
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                        Screen Candidates
                      </>
                    )}
                  </button>

                  <button
                    onClick={() => {
                      setJobId(null);
                      setJobTitle("");
                      setJdText("");
                      setSelectedFile(null);
                      setFileName("");
                      setRequirements(null);
                      setCandidates([]);
                      setSearchComplete(false);
                      setStatus("Draft");
                    }}
                    className="w-full rounded-2xl bg-[#10b981] hover:bg-[#059669] px-4 py-4 text-sm font-bold text-white shadow-lg flex items-center justify-center gap-2 transition-colors border-none"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    Start a New Search
                  </button>

                </div>

              )}

            </section>



            {/* =================================================
                RIGHT SIDE — CANDIDATES
            ================================================= */}

            <section className="glass-dark rounded-[24px] p-6 sm:p-8 xl:col-span-7">

              <div className="mb-6 flex flex-wrap items-center justify-between gap-4">

                <div>

                  <p className="text-xs font-bold uppercase tracking-[0.15em] text-slate-400">
                    Steps 2–3 · Screening
                  </p>

                  <h2 className="mt-1 font-display text-2xl font-bold text-white">
                    Ranked candidates
                  </h2>

                </div>


                <div className="flex items-center gap-3">

                  <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-800 px-3 py-1.5 text-xs font-bold text-white ring-1 ring-slate-700">

                    <span className="text-slate-400">
                      Screened:
                    </span>

                    {searchComplete
                      ? candidates.length
                      : 0}

                  </span>


                  <span className="inline-flex items-center gap-1.5 rounded-full bg-accent/20 px-3 py-1.5 text-xs font-bold text-accent ring-1 ring-accent/30">

                    ✓

                    {searchComplete
                      ? candidates.filter(
                          (candidate) =>
                            Number(
                              candidate.score || 0
                            ) >= 80
                        ).length
                      : 0}

                    {" "}strong

                  </span>

                </div>

              </div>



              {/* =================================================
                  EMPTY STATE
              ================================================= */}

              {!searchComplete &&
                !isSearching && (

                  <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/30 p-12 text-center">

                    <div className="mx-auto mb-4 grid size-14 place-items-center rounded-full bg-slate-800 text-slate-500">

                      <svg
                        className="w-7 h-7"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M21 21l-4.35-4.35m2.35-5.65a8 8 0 11-16 0 8 8 0 0116 0z"
                        />
                      </svg>

                    </div>

                    <p className="text-base font-bold text-white">
                      No candidates yet
                    </p>

                    <p className="mt-2 text-sm text-slate-500">
                      Analyze a job description and search for candidates to see the ranked shortlist.
                    </p>

                  </div>

                )}



              {/* =================================================
                  SEARCHING
              ================================================= */}

              {isSearching && (

                <div className="rounded-2xl border border-slate-700 bg-slate-900/40 p-12 text-center">

                  <svg
                    className="mx-auto size-10 animate-spin text-brand"
                    viewBox="0 0 24 24"
                    fill="none"
                  >

                    <circle
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="3"
                      className="opacity-25"
                    />

                    <path
                      d="M4 12a8 8 0 018-8"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeLinecap="round"
                    />

                  </svg>


                  <p className="mt-4 text-base font-bold text-white">
                    Screening candidates…
                  </p>


                  <p className="mt-2 text-sm text-slate-500">
                    The AI screening engine is evaluating candidates against the job requirements.
                  </p>

                </div>

              )}



              {/* =================================================
                  CANDIDATES
              ================================================= */}

              {searchComplete && (

                <div className="space-y-4">

                  {candidates.length === 0 && (

                    <div className="rounded-2xl border border-slate-700 bg-slate-900/40 p-10 text-center">

                      <p className="font-bold text-white">
                        No matching candidates found.
                      </p>

                      <p className="mt-2 text-sm text-slate-500">
                        Try reviewing the extracted criteria or using a different job description.
                      </p>

                    </div>

                  )}



                  
                  {candidates.length > 0 && (
                    <div className="rounded-2xl border border-slate-700 bg-slate-900/40 p-10 text-center flex flex-col items-center">
                      <div className="mx-auto mb-4 grid size-16 place-items-center rounded-full bg-accent/20 text-accent">
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                      </div>
                      <h3 className="text-xl font-bold text-white mb-2">Screening Complete</h3>
                      <p className="text-slate-400 mb-6">Successfully screened and ranked {candidates.length} candidates against your criteria.</p>
                      
                      <button 
                        onClick={() => setCandidatesModalOpen(true)}
                        className="rounded-xl bg-accent px-6 py-3 text-sm font-bold text-white hover:bg-accent-light transition-colors flex items-center gap-2"
                      >
                        View Screened Candidates
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                      </button>
                    </div>
                  )}

                </div>

              )}

            </section>


          </div>

        </div>

      
        )}
      </main>


      <CompareCandidatesModal 
        isOpen={compareModalOpen} 
        onClose={() => setCompareModalOpen(false)} 
        candidates={candidates} 
        baseCandidateId={compareBaseCandidate} 
      />

      <WhatsappInviteModal
        isOpen={whatsappModalOpen}
        onClose={() => setWhatsappModalOpen(false)}
        candidate={selectedWhatsappCandidate}
        onSend={async (c) => {
          try {
            const cId = c.candidate_id || c.id || c.candidateKey;
            setWhatsappContacted((prev) => ({ ...prev, [cId]: true }));
            handleContact(cId);
          } catch (err) {
            console.error('Failed to mark contacted', err);
          }
        }}
      />

      <JDParsingModal 
        isOpen={jdModalOpen} 
        onClose={() => setJdModalOpen(false)} 
        requirements={requirements}
        job={job}
        formatExperience={formatExperience}
        formatNoticePeriod={formatNoticePeriod}
        formatList={formatList}
      />

    </div>
  );
}

function JDParsingModal({ isOpen, onClose, requirements, job, formatExperience, formatNoticePeriod, formatList }) {
  if (!isOpen || !requirements) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 sm:p-8 backdrop-blur-md overflow-y-auto">
      <div className="w-full max-w-4xl min-h-[50vh] max-h-full rounded-[24px] bg-slate-900 p-8 shadow-2xl relative animate-in fade-in zoom-in-95 duration-200 overflow-y-auto border border-slate-700">
        
        <button 
          onClick={onClose}
          className="absolute top-6 right-6 flex h-10 w-10 items-center justify-center rounded-full bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
        </button>

        <div className="flex gap-4 items-start mb-8 border-b border-slate-700 pb-6">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-blue-500/20 text-blue-400">
            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
          </div>
          <div className="pt-1 text-left">
            <h2 className="text-2xl font-display font-bold text-white">AI-generated search criteria</h2>
            <p className="mt-1 text-sm text-slate-400">Extracted from the job description for accurate candidate matching.</p>
          </div>
        </div>

        <div className="grid gap-4 text-sm">
          {/* EXPERIENCE */}
          <div className="flex items-start gap-4 bg-slate-800/50 p-4 rounded-xl border border-slate-700/50">
            <span className="font-bold text-slate-400 w-32 shrink-0">Experience:</span>
            <span className="font-medium text-white">{formatExperience()}</span>
          </div>

          {/* LOCATION */}
          <div className="flex items-start gap-4 bg-slate-800/50 p-4 rounded-xl border border-slate-700/50">
            <span className="font-bold text-slate-400 w-32 shrink-0">Location:</span>
            <span className="font-medium text-white">{requirements.location || job?.location || "Not specified"}</span>
          </div>

          {/* WORK MODE */}
          <div className="flex items-start gap-4 bg-slate-800/50 p-4 rounded-xl border border-slate-700/50">
            <span className="font-bold text-slate-400 w-32 shrink-0">Work mode:</span>
            <span className="font-medium text-white">{requirements.work_mode || "Not specified"}</span>
          </div>

          {/* NOTICE */}
          <div className="flex items-start gap-4 bg-slate-800/50 p-4 rounded-xl border border-slate-700/50">
            <span className="font-bold text-slate-400 w-32 shrink-0">Notice Period:</span>
            <span className="font-medium text-white">{formatNoticePeriod()}</span>
          </div>

          {/* MANDATORY SKILLS */}
          <div className="flex items-start gap-4 bg-slate-800/50 p-4 rounded-xl border border-slate-700/50">
            <span className="font-bold text-slate-400 w-32 shrink-0">Mandatory Skills:</span>
            <div className="flex flex-wrap gap-2">
              {formatList(requirements.mandatory_skills).map((skill, index) => (
                <span key={`${skill}-${index}`} className="rounded-lg bg-brand/20 px-2.5 py-1 font-bold text-brand ring-1 ring-brand/30">
                  {skill}
                </span>
              ))}
              {!formatList(requirements.mandatory_skills).length && <span className="text-slate-500">None specified</span>}
            </div>
          </div>

          {/* PREFERRED SKILLS */}
          <div className="flex items-start gap-4 bg-slate-800/50 p-4 rounded-xl border border-slate-700/50">
            <span className="font-bold text-slate-400 w-32 shrink-0">Preferred Skills:</span>
            <div className="flex flex-wrap gap-2">
              {formatList(requirements.preferred_skills).map((skill, index) => (
                <span key={`${skill}-${index}`} className="rounded-lg bg-slate-700 px-2.5 py-1 font-bold text-slate-300">
                  {skill}
                </span>
              ))}
              {!formatList(requirements.preferred_skills).length && <span className="text-slate-500">None specified</span>}
            </div>
          </div>

          {/* EDUCATION */}
          {formatList(requirements.education).length > 0 && (
            <div className="flex items-start gap-4 bg-slate-800/50 p-4 rounded-xl border border-slate-700/50">
              <span className="font-bold text-slate-400 w-32 shrink-0">Education:</span>
              <span className="font-medium text-white">{formatList(requirements.education).join(", ")}</span>
            </div>
          )}

          {/* CERTIFICATIONS */}
          {formatList(requirements.certifications).length > 0 && (
            <div className="flex items-start gap-4 bg-slate-800/50 p-4 rounded-xl border border-slate-700/50">
              <span className="font-bold text-slate-400 w-32 shrink-0">Certifications:</span>
              <span className="font-medium text-white">{formatList(requirements.certifications).join(", ")}</span>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}