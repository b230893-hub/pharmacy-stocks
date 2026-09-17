import { useState, useEffect, useCallback } from 'react';

const API_BASE = 'http://localhost:8000';

function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [view, setView] = useState('login'); // login, dashboard
  
  if (!token) {
    return <AuthScreen setToken={setToken} view={view} setView={setView} />;
  }
  return <Dashboard token={token} setToken={setToken} />;
}

function AuthScreen({ setToken, view, setView }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    try {
      const endpoint = view === 'login' ? '/token' : '/register';
      const body = view === 'login' 
        ? new URLSearchParams({ username, password })
        : JSON.stringify({ username, password });
      
      const headers = view === 'login' 
        ? { 'Content-Type': 'application/x-www-form-urlencoded' }
        : { 'Content-Type': 'application/json' };

      const res = await fetch(`${API_BASE}${endpoint}`, { method: 'POST', headers, body });
      const data = await res.json();
      
      if (!res.ok) throw new Error(data.detail || 'Authentication failed');
      
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="flex h-screen items-center justify-center">
      <form onSubmit={handleSubmit} className="bg-white p-8 rounded shadow-md w-96">
        <h2 className="text-2xl font-bold mb-6">{view === 'login' ? 'Login' : 'Register'}</h2>
        {error && <p className="text-red-500 mb-4 text-sm">{error}</p>}
        <input className="w-full border p-2 mb-4 rounded" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} required />
        <input className="w-full border p-2 mb-6 rounded" type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} required />
        <button className="w-full bg-blue-600 text-white p-2 rounded">{view === 'login' ? 'Login' : 'Register'}</button>
        <p className="mt-4 text-sm text-center">
          {view === 'login' ? "Don't have an account? " : "Already have an account? "}
          <button type="button" className="text-blue-600" onClick={() => setView(view === 'login' ? 'register' : 'login')}>
            {view === 'login' ? 'Register here' : 'Login here'}
          </button>
        </p>
      </form>
    </div>
  );
}

function Dashboard({ token, setToken }) {
  const [medicines, setMedicines] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const LIMIT = 10;
  
  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchData = useCallback(async () => {
    try {
      const [medRes, alertRes] = await Promise.all([
        fetch(`${API_BASE}/medicines/?skip=${page * LIMIT}&limit=${LIMIT}&search=${search}`, { headers }),
        fetch(`${API_BASE}/alerts/expiring/`, { headers })
      ]);
      if (medRes.status === 401) return logout();
      
      const meds = await medRes.json();
      const alts = await alertRes.json();
      setMedicines(meds);
      setAlerts(alts);
    } catch (err) {
      console.error(err);
    }
  }, [page, search, token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const logout = () => {
    localStorage.removeItem('token');
    setToken('');
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">FEFO Pharmacy Inventory</h1>
        <button onClick={logout} className="bg-red-500 text-white px-4 py-2 rounded">Logout</button>
      </div>

      {alerts.length > 0 && (
        <div className="bg-orange-100 border-l-4 border-orange-500 p-4 mb-8 rounded">
          <h3 className="font-bold text-orange-700">Expiring Soon (30 Days)</h3>
          <ul className="mt-2 text-sm text-orange-800">
            {alerts.map(a => (
              <li key={a.batch_id}>
                {a.medicine_name} - Batch {a.batch_number} expires in {a.days_to_expiry} days ({a.quantity} units left)
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mb-4 flex gap-4">
        <input 
          className="border p-2 rounded flex-grow" 
          placeholder="Search medicines..." 
          value={search} 
          onChange={e => {setSearch(e.target.value); setPage(0);}} 
        />
        <AddMedicineModal headers={headers} refresh={fetchData} />
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="w-full text-left">
          <thead className="bg-gray-100">
            <tr>
              <th className="p-4">Name</th>
              <th className="p-4">Description</th>
              <th className="p-4">Unexpired Stock</th>
              <th className="p-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {medicines.map(med => (
              <tr key={med.id} className="border-t">
                <td className="p-4 font-semibold">{med.name}</td>
                <td className="p-4 text-gray-600">{med.description}</td>
                <td className="p-4">
                  <span className={`px-2 py-1 rounded text-sm ${med.total_unexpired_stock > 0 ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                    {med.total_unexpired_stock} units
                  </span>
                </td>
                <td className="p-4 flex gap-2">
                  <AddBatchModal medicineId={med.id} headers={headers} refresh={fetchData} />
                  <DispenseModal medicineId={med.id} medicineName={med.name} stock={med.total_unexpired_stock} headers={headers} refresh={fetchData} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      <div className="mt-4 flex justify-between">
        <button disabled={page === 0} onClick={() => setPage(p => p - 1)} className="bg-gray-200 px-4 py-2 rounded disabled:opacity-50">Previous</button>
        <button onClick={() => setPage(p => p + 1)} className="bg-gray-200 px-4 py-2 rounded">Next</button>
      </div>
    </div>
  );
}

function AddMedicineModal({ headers, refresh }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    await fetch(`${API_BASE}/medicines/`, {
      method: 'POST', headers, body: JSON.stringify({ name, description: desc })
    });
    setOpen(false); setName(''); setDesc(''); refresh();
  };

  return (
    <>
      <button onClick={() => setOpen(true)} className="bg-blue-600 text-white px-4 py-2 rounded">Add Medicine</button>
      {open && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <form onSubmit={submit} className="bg-white p-6 rounded shadow-lg w-96">
            <h2 className="text-xl font-bold mb-4">New Medicine</h2>
            <input className="w-full border p-2 mb-2 rounded" placeholder="Name" value={name} onChange={e => setName(e.target.value)} required />
            <input className="w-full border p-2 mb-4 rounded" placeholder="Description" value={desc} onChange={e => setDesc(e.target.value)} required />
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 bg-gray-200 rounded">Cancel</button>
              <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded">Save</button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}

function AddBatchModal({ medicineId, headers, refresh }) {
  const [open, setOpen] = useState(false);
  const [batchNo, setBatchNo] = useState('');
  const [qty, setQty] = useState('');
  const [expiry, setExpiry] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    await fetch(`${API_BASE}/medicines/${medicineId}/batches/`, {
      method: 'POST', headers, body: JSON.stringify({ batch_number: batchNo, quantity: parseInt(qty), expiry_date: expiry })
    });
    setOpen(false); setBatchNo(''); setQty(''); setExpiry(''); refresh();
  };

  return (
    <>
      <button onClick={() => setOpen(true)} className="text-sm bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded">Add Batch</button>
      {open && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <form onSubmit={submit} className="bg-white p-6 rounded shadow-lg w-96">
            <h2 className="text-xl font-bold mb-4">Add Batch</h2>
            <input className="w-full border p-2 mb-2 rounded" placeholder="Batch Number" value={batchNo} onChange={e => setBatchNo(e.target.value)} required />
            <input className="w-full border p-2 mb-2 rounded" type="number" placeholder="Quantity" value={qty} onChange={e => setQty(e.target.value)} required min="1" />
            <input className="w-full border p-2 mb-4 rounded" type="date" value={expiry} onChange={e => setExpiry(e.target.value)} required />
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 bg-gray-200 rounded">Cancel</button>
              <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded">Save</button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}

function DispenseModal({ medicineId, medicineName, stock, headers, refresh }) {
  const [open, setOpen] = useState(false);
  const [qty, setQty] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess(null);
    const res = await fetch(`${API_BASE}/medicines/${medicineId}/dispense/`, {
      method: 'POST', headers, body: JSON.stringify({ quantity: parseInt(qty) })
    });
    const data = await res.json();
    if (!res.ok) {
      setError(data.detail);
    } else {
      setSuccess(data.details);
      setQty('');
      refresh();
    }
  };

  return (
    <>
      <button onClick={() => {setOpen(true); setError(''); setSuccess(null);}} disabled={stock === 0} className="text-sm bg-blue-100 hover:bg-blue-200 text-blue-800 px-3 py-1 rounded disabled:opacity-50">Dispense</button>
      {open && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <div className="bg-white p-6 rounded shadow-lg w-96">
            <h2 className="text-xl font-bold mb-2">Dispense {medicineName}</h2>
            <p className="text-sm text-gray-600 mb-4">Available: {stock} units</p>
            
            {error && <p className="text-red-500 text-sm mb-2">{error}</p>}
            {success && (
              <div className="bg-green-100 text-green-800 p-2 text-sm rounded mb-4">
                <p className="font-bold">Dispensed from batches:</p>
                <ul className="list-disc ml-4">
                  {success.map((s, i) => <li key={i}>{s.batch_number}: {s.quantity_dispensed} units</li>)}
                </ul>
              </div>
            )}
            
            <form onSubmit={submit}>
              <input className="w-full border p-2 mb-4 rounded" type="number" placeholder="Quantity to dispense" value={qty} onChange={e => setQty(e.target.value)} required min="1" max={stock} />
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 bg-gray-200 rounded">Close</button>
                <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded">Dispense (FEFO)</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

export default App;