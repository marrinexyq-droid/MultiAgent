const featureCards = [
  {
    "title": "SECTION RHYTHM",
    "text": "Inferred 6 main sections from the screenshot's vertical transitions."
  },
  {
    "title": "COLOR SYSTEM",
    "text": "Primary color adapts to #FBEDE5 with accent support from #FF7C4C."
  },
  {
    "title": "PAGE TYPE",
    "text": "The local analyzer classified this input as a editorial layout and changed the composition accordingly."
  }
];

        const proofItems = [
  "EDITORIAL COMPOSITION",
  "LIGHT SURFACE SYSTEM",
  "6 INFERRED CONTENT BANDS",
  "DESKTOP-FIRST GENERATED OUTPUT"
];

        export default function App() {
          return (
            <div className="page-shell">
              <div className="announcement-bar">
                <div className="container announcement-copy">
                  <span>NOW SUPPORTING IMAGE-TO-REACT WORKFLOWS</span>
                  <span>TURN LONG SCREENSHOTS INTO LIVE PAGES</span>
                </div>
              </div>

              <header className="site-header">
                <div className="container nav-row">
                  <a className="brand-mark" href="#top">DUCK/STACK</a>
                  <nav className="nav-links">
                    <a href="#features">PRODUCT</a>
                    <a href="#system">SYSTEM</a>
                    <a href="#stories">STORIES</a>
                    <a href="#contact">LOGIN</a>
                  </nav>
                  <a className="button-shadow small" href="#contact">
                    <span className="button-face primary">START FREE →</span>
                  </a>
                </div>
              </header>

              <main id="top">
                <section className="hero-section container">
                  <div className="hero-copy">
                    <div className="eyebrow">REFERENCE-DRIVEN LANDING PAGE</div>
                    <h1>BUILD A PAGE FROM A VISUAL REFERENCE</h1>
                    <p>The stub generator inferred a longer marketing-style composition and shifted toward larger sections, stronger hero emphasis, and broader storytelling space.</p>
                    <div className="hero-actions">
                      <a className="button-shadow" href="#contact">
                        <span className="button-face primary">BUILD THE PAGE →</span>
                      </a>
                      <a className="button-shadow" href="#features">
                        <span className="button-face secondary">SEE THE SYSTEM</span>
                      </a>
                    </div>
                  </div>

                  <div className="hero-card">
                    <div className="hero-card-label">REFERENCE ANALYSIS</div>
                    <div className="hero-card-grid">
                      <div>
                        <span className="stat-label">MODE</span>
                        <strong>GENERALIZED</strong>
                      </div>
                      <div>
                        <span className="stat-label">GOAL</span>
                        <strong>ADAPTIVE LANDING PAGE</strong>
                      </div>
                      <div>
                        <span className="stat-label">STYLE</span>
                        <strong>GENERALIZED</strong>
                      </div>
                      <div>
                        <span className="stat-label">STACK</span>
                        <strong>REACT + CSS</strong>
                      </div>
                    </div>
                    <div className="cloud cloud-a" />
                    <div className="cloud cloud-b" />
                  </div>
                </section>

                <section className="marquee-band yellow-band" aria-label="Scrolling banner">
                  <div className="marquee-track">
                    <span>QUERY FASTER • COLLABORATE SMOOTHER • SHIP WARMER UI •</span>
                    <span>QUERY FASTER • COLLABORATE SMOOTHER • SHIP WARMER UI •</span>
                    <span>QUERY FASTER • COLLABORATE SMOOTHER • SHIP WARMER UI •</span>
                  </div>
                </section>

                <section className="feature-section container" id="features">
                    <div className="section-label">WHY THIS MATCHES THE INPUT</div>
                  <div className="section-heading">
                    <h2>THE PAGE LEANS OPEN AND SECTIONAL</h2>
                    <p>
                      The stub generator inferred a longer marketing-style composition and shifted toward larger sections, stronger hero emphasis, and broader storytelling space.
                    </p>
                  </div>
                  <div className="feature-grid">
                    {featureCards.map((card) => (
                      <article className="feature-card" key={card.title}>
                        <div className="card-illustration" />
                        <h3>{card.title}</h3>
                        <p>{card.text}</p>
                        <a href="#system">LEARN MORE →</a>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="marquee-band teal-band" aria-label="Scrolling banner">
                  <div className="marquee-track reverse">
                    <span>STRUCTURE • RHYTHM • BORDERS • WARMTH • MOTION •</span>
                    <span>STRUCTURE • RHYTHM • BORDERS • WARMTH • MOTION •</span>
                    <span>STRUCTURE • RHYTHM • BORDERS • WARMTH • MOTION •</span>
                  </div>
                </section>

                <section className="system-section container" id="system">
                  <div className="system-sidebar">
                    <div className="section-label dark">DESIGN SYSTEM</div>
                    <h2>ONE VISUAL LANGUAGE, MANY SECTION TYPES</h2>
                    <p>
                      The screenshot suggested a more spacious storytelling rhythm, so the stub keeps broader hero spacing, banners, and card-led sections.
                    </p>
                    <a className="text-link" href="#contact">REQUEST A CUSTOM BUILD →</a>
                  </div>
                  <div className="proof-panel">
                    {proofItems.map((item) => (
                      <div className="proof-row" key={item}>
                        <span>{item}</span>
                        <span>OK</span>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="contact-section container" id="contact">
                  <div className="section-label coral">START WITH A SCREENSHOT</div>
                  <div className="contact-card">
                    <div className="contact-copy">
                      <h2>DROP IN THE REFERENCE, PICK A MODE, AND GENERATE A PAGE</h2>
                      <p>
                        This starter output is ready for replacement with model-generated content or your own production copy. Keep the typography and border system stable while iterating.
                      </p>
                    </div>
                    <form className="contact-form">
                      <label>
                        <span>EMAIL</span>
                        <input type="email" placeholder="team@example.com" />
                      </label>
                      <button type="button" className="button-shadow">
                        <span className="button-face primary">BOOK A BUILD →</span>
                      </button>
                    </form>
                  </div>
                </section>
              </main>

              <footer className="site-footer">
                <div className="container footer-grid">
                  <div>
                    <div className="footer-heading">REFERENCE/STACK</div>
                    <p>A locally adaptive front-end generation starter that shifts layout and color based on the uploaded screenshot.</p>
                  </div>
                  <div>
                    <div className="footer-heading">PRODUCT</div>
                    <a href="#features">Features</a>
                    <a href="#system">System</a>
                  </div>
                  <div>
                    <div className="footer-heading">WORKFLOW</div>
                    <a href="#top">Generalized</a>
                    <a href="#top">High Fidelity</a>
                  </div>
                  <div>
                    <div className="footer-heading">CONTACT</div>
                    <a href="#contact">Start Free</a>
                    <a href="#contact">Talk to Sales</a>
                  </div>
                </div>
              </footer>
            </div>
          );
        }
