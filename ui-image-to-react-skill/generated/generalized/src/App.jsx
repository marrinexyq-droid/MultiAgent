import React from 'react';
import './index.css';

function App() {
  return (
    <div className="app">
      <header className="header">
        <div className="top-bar">
          <div className="logo">MotherDuck</div>
          <nav className="nav">
            <a href="#">Product</a>
            <a href="#">Community</a>
            <a href="#">Company</a>
            <a href="#">Docs</a>
            <a href="#">Pricing</a>
            <a href="#">Contact Us</a>
          </nav>
          <div className="auth-buttons">
            <button className="login">Log In</button>
            <button className="start-free">Start Free</button>
          </div>
        </div>
      </header>
      <main className="main">
        <section className="hero">
          <h1>Infrastructure for Answers</h1>
          <p>The cloud data warehouse built for answers, in SQL or natural language. Fast, serverless analytics powered by DuckDB—from production apps to internal insights.</p>
          <div className="cta-buttons">
            <button className="try-free">Try 7 Days Free</button>
            <button className="book-demo">Book a Demo</button>
          </div>
        </section>
        <section className="reports">
          <h2>Choose a Report to Start</h2>
          <div className="report-cards">
            <div className="card">Sales by Product</div>
            <div className="card">Regional Sales</div>
            <div className="card">Customer Health</div>
          </div>
        </section>
      </main>
      <footer className="footer">
        <p>© 2026 MotherDuck. All rights reserved.</p>
      </footer>
    </div>
  );
}

export default App;