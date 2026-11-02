import Copilot from "../components/Copilot";

const SUGGESTIONS = [
  { tag: "External lane · allowed", q: "What's happening with Canadian interest rates, and how do our current GIC rates compare?" },
  { tag: "External lane · allowed", q: "Summarize our policy on mortgage prepayment privileges." },
  { tag: "Data guard · will be blocked", q: "Daniel Okafor has $86,000 sitting in savings and is retiring in 2028. What should he do with it?" },
];

export default function Research({ user }) {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Research</h1>
          <p>General questions with no client data may use the external model lane. The gateway blocks client data before it leaves.</p>
        </div>
      </div>
      <div style={{ maxWidth: 860 }}>
        <Copilot mode="research" user={user} suggestions={SUGGESTIONS} full />
      </div>
    </>
  );
}
