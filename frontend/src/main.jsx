import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import ExecutiveReportPage from './pages/ExecutiveReportPage';
import './index.css';

const path = window.location.pathname.replace(/\/+$/, '') || '/';
const RootComponent = path === '/executive-report' || path === '/relatorio-executivo' ? ExecutiveReportPage : App;

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <RootComponent />
  </React.StrictMode>,
);
