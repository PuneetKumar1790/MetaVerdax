import Navbar from '../components/Navbar';
import HeroSection from '../components/HeroSection';
import ProblemSection from '../components/ProblemSection';
import HowItWorks from '../components/HowItWorks';
import OpenMetadataMCP from '../components/OpenMetadataMCP';
import DemoTerminal from '../components/DemoTerminal';
import ComparisonTable from '../components/ComparisonTable';
import ArchitectureDiagram from '../components/ArchitectureDiagram';
import ResourcesSection from '../components/ResourcesSection';
import Footer from '../components/Footer';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-brand-black">
      <Navbar />
      <HeroSection />
      <ProblemSection />
      <HowItWorks />
      <OpenMetadataMCP />
      <DemoTerminal />
      <ComparisonTable />
      <ArchitectureDiagram />
      <ResourcesSection />
      <Footer />
    </div>
  );
}
