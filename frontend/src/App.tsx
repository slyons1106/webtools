import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { NavigationBar } from './components/NavigationBar';
import { LogSearchPage } from './pages/LogSearchPage';
import { S3ViewerPage } from './pages/S3ViewerPage';
import { CSVSplitterPage } from './pages/CSVSplitterPage';
import { PersonDetailsPage } from './pages/PersonDetailsPage';
import { ToolsPage } from './pages/ToolsPage';
import { LabelsPage } from './pages/LabelsPage';
import { ICCIDLookupPage } from './pages/ICCIDLookupPage';

function App() {
  return (
    <Router>
      <div className="App d-flex flex-column">
        <NavigationBar />
        <main className="flex-grow-1 overflow-auto">
          <Routes>
            <Route path="/" element={<LabelsPage />} />
            <Route path="/person-details" element={<PersonDetailsPage />} />
            <Route path="/log-search" element={<LogSearchPage />} />
            <Route path="/iccid-lookup" element={<ICCIDLookupPage />} />
            <Route path="/s3-viewer" element={<S3ViewerPage />} />
            <Route path="/csv-splitter" element={<CSVSplitterPage />} />
            <Route path="/tools" element={<ToolsPage />} />
            <Route path="/labels" element={<LabelsPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;