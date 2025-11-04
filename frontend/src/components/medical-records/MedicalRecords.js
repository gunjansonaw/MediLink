import React, { useState, useEffect } from 'react';
import { FileText, Plus } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import api from '../../services/api';
import './MedicalRecords.css';

function MedicalRecords() {
  const { user } = useAuth();
  const [records, setRecords] = useState([]);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRecords();
  }, []);

  const fetchRecords = async () => {
    try {
      const endpoint = user.role === 'patient' 
        ? '/medical-records/records/my_records/' 
        : '/medical-records/records/';
      const response = await api.get(endpoint);
      setRecords(response.data.results || response.data);
    } catch (error) {
      console.error('Error fetching records:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading medical records...</div>;
  }

  return (
    <div className="medical-records-page">
      <div className="page-header">
        <h1>Medical Records</h1>
      </div>

      <div className="records-container">
        <div className="records-list">
          {records.length === 0 ? (
            <div className="card">
              <p className="no-data">No medical records found</p>
            </div>
          ) : (
            records.map((record) => (
              <div
                key={record.id}
                className={`record-card ${selectedRecord?.id === record.id ? 'active' : ''}`}
                onClick={() => setSelectedRecord(record)}
              >
                <div className="record-header">
                  <FileText size={20} />
                  <div>
                    <h3>{record.diagnosis}</h3>
                    <p className="record-date">
                      {new Date(record.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <p className="record-doctor">
                  Dr. {record.doctor_details?.first_name} {record.doctor_details?.last_name}
                </p>
              </div>
            ))
          )}
        </div>

        {selectedRecord && (
          <div className="record-details card">
            <h2>Medical Record Details</h2>
            
            <div className="detail-section">
              <h3>Patient Information</h3>
              <p><strong>Name:</strong> {selectedRecord.patient_details?.first_name} {selectedRecord.patient_details?.last_name}</p>
              <p><strong>Date:</strong> {new Date(selectedRecord.created_at).toLocaleDateString()}</p>
              <p><strong>Doctor:</strong> Dr. {selectedRecord.doctor_details?.first_name} {selectedRecord.doctor_details?.last_name}</p>
            </div>

            <div className="detail-section">
              <h3>Diagnosis</h3>
              <p>{selectedRecord.diagnosis}</p>
            </div>

            <div className="detail-section">
              <h3>Symptoms</h3>
              <p>{selectedRecord.symptoms}</p>
            </div>

            <div className="detail-section">
              <h3>Treatment Plan</h3>
              <p>{selectedRecord.treatment_plan}</p>
            </div>

            {selectedRecord.prescriptions && selectedRecord.prescriptions.length > 0 && (
              <div className="detail-section">
                <h3>Prescriptions</h3>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Medication</th>
                      <th>Dosage</th>
                      <th>Frequency</th>
                      <th>Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedRecord.prescriptions.map((prescription) => (
                      <tr key={prescription.id}>
                        <td>{prescription.medication_name}</td>
                        <td>{prescription.dosage}</td>
                        <td>{prescription.frequency}</td>
                        <td>{prescription.duration}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {selectedRecord.lab_tests && selectedRecord.lab_tests.length > 0 && (
              <div className="detail-section">
                <h3>Lab Tests</h3>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Test Name</th>
                      <th>Type</th>
                      <th>Status</th>
                      <th>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedRecord.lab_tests.map((test) => (
                      <tr key={test.id}>
                        <td>{test.test_name}</td>
                        <td>{test.test_type}</td>
                        <td>
                          <span className={`badge badge-${
                            test.status === 'completed' ? 'success' : 'warning'
                          }`}>
                            {test.status}
                          </span>
                        </td>
                        <td>{test.result || 'Pending'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {selectedRecord.notes && (
              <div className="detail-section">
                <h3>Additional Notes</h3>
                <p>{selectedRecord.notes}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default MedicalRecords;
