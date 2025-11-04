import React, { useState, useEffect } from 'react';
import { Calendar, Plus, Check, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import api from '../../services/api';
import './Appointments.css';

function Appointments() {
  const { user } = useAuth();
  const [appointments, setAppointments] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState({
    doctor: '',
    appointment_date: '',
    appointment_time: '',
    reason: '',
  });

  useEffect(() => {
    fetchAppointments();
    if (user.role === 'patient') {
      fetchDoctors();
    }
  }, [user.role]);

  const fetchAppointments = async () => {
    try {
      const response = await api.get('/appointments/appointments/');
      setAppointments(response.data.results || response.data);
    } catch (error) {
      console.error('Error fetching appointments:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchDoctors = async () => {
    try {
      const response = await api.get('/users/doctors/');
      setDoctors(response.data);
    } catch (error) {
      console.error('Error fetching doctors:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/appointments/appointments/', formData);
      setShowModal(false);
      fetchAppointments();
      setFormData({ doctor: '', appointment_date: '', appointment_time: '', reason: '' });
    } catch (error) {
      console.error('Error creating appointment:', error);
      alert('Failed to create appointment');
    }
  };

  const handleConfirm = async (id) => {
    try {
      await api.post(`/appointments/appointments/${id}/confirm/`);
      fetchAppointments();
    } catch (error) {
      console.error('Error confirming appointment:', error);
    }
  };

  const handleCancel = async (id) => {
    if (window.confirm('Are you sure you want to cancel this appointment?')) {
      try {
        await api.post(`/appointments/appointments/${id}/cancel/`);
        fetchAppointments();
      } catch (error) {
        console.error('Error cancelling appointment:', error);
      }
    }
  };

  if (loading) {
    return <div className="loading">Loading appointments...</div>;
  }

  return (
    <div className="appointments-page">
      <div className="page-header">
        <h1>Appointments</h1>
        {user.role === 'patient' && (
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={20} />
            Book Appointment
          </button>
        )}
      </div>

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Time</th>
              {user.role !== 'doctor' && <th>Doctor</th>}
              {user.role !== 'patient' && <th>Patient</th>}
              <th>Reason</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {appointments.length === 0 ? (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center' }}>No appointments found</td>
              </tr>
            ) : (
              appointments.map((appointment) => (
                <tr key={appointment.id}>
                  <td>{appointment.appointment_date}</td>
                  <td>{appointment.appointment_time}</td>
                  {user.role !== 'doctor' && (
                    <td>Dr. {appointment.doctor_details?.first_name} {appointment.doctor_details?.last_name}</td>
                  )}
                  {user.role !== 'patient' && (
                    <td>{appointment.patient_details?.first_name} {appointment.patient_details?.last_name}</td>
                  )}
                  <td>{appointment.reason}</td>
                  <td>
                    <span className={`badge badge-${
                      appointment.status === 'completed' ? 'success' :
                      appointment.status === 'confirmed' ? 'info' :
                      appointment.status === 'cancelled' ? 'danger' : 'warning'
                    }`}>
                      {appointment.status}
                    </span>
                  </td>
                  <td>
                    <div className="action-buttons">
                      {user.role === 'doctor' && appointment.status === 'scheduled' && (
                        <button
                          className="btn btn-success btn-sm"
                          onClick={() => handleConfirm(appointment.id)}
                        >
                          <Check size={16} />
                        </button>
                      )}
                      {appointment.status !== 'cancelled' && appointment.status !== 'completed' && (
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleCancel(appointment.id)}
                        >
                          <X size={16} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Book Appointment</h2>
              <button className="close-btn" onClick={() => setShowModal(false)}>×</button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>Doctor</label>
                <select
                  value={formData.doctor}
                  onChange={(e) => setFormData({ ...formData, doctor: e.target.value })}
                  required
                >
                  <option value="">Select Doctor</option>
                  {doctors.map((doctor) => (
                    <option key={doctor.id} value={doctor.id}>
                      Dr. {doctor.first_name} {doctor.last_name} - {doctor.doctor_profile?.specialization}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Date</label>
                <input
                  type="date"
                  value={formData.appointment_date}
                  onChange={(e) => setFormData({ ...formData, appointment_date: e.target.value })}
                  required
                  min={new Date().toISOString().split('T')[0]}
                />
              </div>
              <div className="form-group">
                <label>Time</label>
                <input
                  type="time"
                  value={formData.appointment_time}
                  onChange={(e) => setFormData({ ...formData, appointment_time: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>Reason</label>
                <textarea
                  value={formData.reason}
                  onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
                  required
                  rows="3"
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Book Appointment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default Appointments;
