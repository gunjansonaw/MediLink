import React from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { 
  Heart, Calendar, FileText, DollarSign, 
  LogOut, Menu, X 
} from 'lucide-react';
import './Layout.css';

function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = React.useState(true);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getNavItems = () => {
    const baseUrl = `/${user.role}`;
    
    const items = [
      { path: `${baseUrl}/dashboard`, icon: <Heart size={20} />, label: 'Dashboard' },
      { path: `${baseUrl}/appointments`, icon: <Calendar size={20} />, label: 'Appointments' },
      { path: `${baseUrl}/medical-records`, icon: <FileText size={20} />, label: 'Medical Records' },
    ];

    if (user.role === 'admin' || user.role === 'patient') {
      items.push({ path: `${baseUrl}/billing`, icon: <DollarSign size={20} />, label: 'Billing' });
    }

    return items;
  };

  return (
    <div className="layout">
      <aside className={`sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
        <div className="sidebar-header">
          <Heart size={32} />
          <h2>MediLink</h2>
        </div>

        <nav className="sidebar-nav">
          {getNavItems().map((item) => (
            <Link key={item.path} to={item.path} className="nav-item">
              {item.icon}
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button onClick={handleLogout} className="logout-btn">
            <LogOut size={20} />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      <div className="main-content">
        <header className="header">
          <button 
            className="menu-toggle" 
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
          </button>

          <div className="header-user">
            <div className="user-info">
              <span className="user-name">{user.first_name} {user.last_name}</span>
              <span className="user-role">{user.role}</span>
            </div>
          </div>
        </header>

        <main className="content">
          {children}
        </main>
      </div>
    </div>
  );
}

export default Layout;
