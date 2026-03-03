# 🚀 LANMEET  
## Local Area Network (LAN) Based Video Conferencing Application

LANMEET is a Python-based real-time video conferencing system that enables seamless communication between devices connected to the same Local Area Network (LAN). Unlike traditional platforms such as Zoom or Google Meet, LANMEET operates entirely without internet access. It uses socket programming and real-time multimedia transmission to allow devices within the same network to communicate efficiently and securely.

This project demonstrates strong practical implementation of Computer Networks concepts including socket programming, client-server architecture, concurrency handling, and real-time data streaming.

---

# 📌 Project Overview

Modern video conferencing platforms rely on cloud servers and internet connectivity. However, in many environments such as classrooms, labs, offices, or secure facilities, communication is often required within a closed internal network.

LANMEET solves this problem by:

- Eliminating the need for internet connectivity  
- Enabling real-time communication within the same LAN  
- Providing low-latency internal video streaming  
- Demonstrating distributed system communication principles  

---

# 🎯 Problem Statement

Design and implement a Zoom-like video communication application that:

- Works only inside a local network  
- Uses socket programming for device communication  
- Streams live video frames in real-time  
- Supports multiple clients connected to a central server  
- Does not depend on any cloud infrastructure  

---

# 🏗 System Architecture

LANMEET follows a Client-Server Model.

1. One machine acts as the Server.
2. Multiple machines act as Clients.
3. Clients connect using the server’s local IP address.
4. Video frames are captured, encoded, transmitted, decoded, and displayed in real-time.

Communication Flow:

Client → Server → Broadcast → All Connected Clients

Functional Steps:

1. Capture video frame from webcam.
2. Convert frame into serialized byte format.
3. Send frame through socket connection.
4. Server receives frame.
5. Server redistributes frame to connected clients.
6. Clients decode and display the frame.

---

# 🧠 Technical Implementation

## Socket Programming
- Establishes reliable communication between server and clients.
- Manages connection requests.
- Transfers video frame data over network.
- Handles concurrent client connections.

## Real-Time Video Streaming
- Continuous frame capture using OpenCV.
- Frame serialization for transmission.
- Reconstruction of frames on receiving side.

## Concurrency Handling
- Threads manage multiple client connections.
- Ensures smooth real-time performance.
- Prevents blocking during send/receive operations.

## Data Transmission Logic
- Frame converted into byte stream.
- Frame size sent before actual frame data.
- Receiver reconstructs frame using size header.
- Decoded frame displayed using OpenCV.

---

# ✨ Features

- Real-time video conferencing over LAN
- No internet required
- Low-latency communication
- Client-server architecture
- Multi-client support (if implemented)
- Lightweight and efficient design
- Simple execution via terminal

---

# 🛠 Technologies Used

- Python
- Socket Programming (TCP/UDP)
- OpenCV
- Threading / Multiprocessing
- Data Serialization (e.g., pickle/struct if used)
- NumPy (for frame handling)

---

# ⚙️ Installation & Setup

## 1️⃣ Clone Repository

git clone https://github.com/ayush10mishra/LANMEET.git  
cd LANMEET  

## 2️⃣ Install Dependencies

pip install -r requirements.txt  

If requirements.txt is not available:

pip install opencv-python numpy  

---

# ▶️ How to Run

## Start Server

python server.py  

The server will start listening for incoming connections.

## Start Client (on other systems connected to same LAN)

python client.py  

Enter the server's local IP address when prompted.

---

# 🌐 Network Configuration

All systems must be connected to:

- Same WiFi network  
OR  
- Same Ethernet LAN  

To find Server IP:

On Linux:
ifconfig  

On Windows:
ipconfig  

Use the IPv4 address of the server machine (example: 192.168.1.5).

---

# 📂 Project Structure

LANMEET/  
│  
├── server.py  
├── client.py  
├── requirements.txt  
├── README.md  
└── .gitignore  

---

# 🚧 Challenges Faced

- Efficient transmission of large video frames  
- Handling multiple concurrent connections  
- Preventing frame drops and corruption  
- Reducing latency in streaming  
- Synchronizing client-server communication  
- Maintaining stable socket connections  

---

# 🚀 Future Improvements

- Audio communication integration  
- Screen sharing feature  
- Text chat functionality  
- GUI using Tkinter or PyQt  
- End-to-end encryption  
- File sharing over LAN  
- Performance optimization  
- Adaptive frame compression  

---

# 🎓 Learning Outcomes

Through this project, the following concepts were practically implemented:

- Computer Networks fundamentals  
- TCP/IP communication  
- Client-server system design  
- Real-time streaming systems  
- Concurrent programming  
- Multimedia data handling  
- Distributed system communication  

---

# 🔥 Why This Project Is Significant

LANMEET bridges theoretical networking concepts with real-world system implementation. It showcases practical understanding of socket programming, network communication, concurrency, and multimedia streaming — making it a strong academic and resume-level Computer Networks project.

---

# 👨‍💻 Author

Ayush Mishra  
B.Tech – Computer Science  
Interest Areas: Computer Networks, Systems, Machine Learning  

GitHub: https://github.com/ayush10mishra  

---

# 📜 License

This project is developed for educational and academic purposes.
