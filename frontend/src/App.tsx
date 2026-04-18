import { Routes, Route } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import AppDashboard from './pages/AppDashboard';

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/app/*" element={<AppDashboard />} />
    </Routes>
  );
}

export default App;
