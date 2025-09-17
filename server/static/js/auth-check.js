import { initializeApp } from "https://www.gstatic.com/firebasejs/11.6.1/firebase-app.js";
import { getAuth, onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/11.6.1/firebase-auth.js";

const firebaseConfig = {
    apiKey: "AIzaSyCTbjfadYocNBVdQpo_KzuW5JEtZS38Pkw",
    authDomain: "bookhub-80381.firebaseapp.com",
    projectId: "bookhub-80381",
    storageBucket: "bookhub-80381.firebasestorage.app",
    messagingSenderId: "525454852384",
    appId: "1:525454852384:web:1910c936f8062125779745",
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// Global variable to store the current user's ID token
window.currentUserIdToken = null;


const userIdDisplay = document.getElementById("userIdDisplay");
const loginTab = document.getElementById("loginTab");
const registerTab = document.getElementById("registerTab");
const logoutButton = document.getElementById("logoutButton");
const logoutLink = document.getElementById("logoutLink");

// Hide auth controls initially until auth state is known
const authControls = document.querySelector('.auth-controls');
if (authControls) {
    authControls.style.visibility = 'hidden';
}

function setupLogoutHandler() {
    if (logoutLink) {
        logoutLink.addEventListener("click", async () => {
            try {
                await signOut(auth);
                window.location.reload(true);
            } catch (error) {
                console.error("Error during sign out:", error);
                alert("Error signing out. Please try again.");
            }
        });
        console.log("Displayed logoutLink and attached click handler");
    }
}

function updateUserDisplay(user) {
    if (!userIdDisplay) return;

    const loginLink = document.getElementById("loginLink");
    const registerLink = document.getElementById("registerLink");
    const logoutLink = document.getElementById("logoutLink");

    if (user) {
        if (user.email) {
            userIdDisplay.textContent = `Welcome, ${user.email}`;
            if (loginLink) loginLink.style.display = "none";
            if (registerLink) registerLink.style.display = "none";
            if (logoutLink) logoutLink.style.display = "inline";
        } else {
            userIdDisplay.textContent = `User ID: ${user.uid} (Guest)`;
            if (loginLink) loginLink.style.display = "inline";
            if (registerLink) registerLink.style.display = "inline";
            if (logoutLink) logoutLink.style.display = "none";
        }
        userIdDisplay.style.display = "inline-block";
    } else {
        userIdDisplay.textContent = "";
        userIdDisplay.style.display = "none";
        if (loginLink) loginLink.style.display = "inline";
        if (registerLink) registerLink.style.display = "inline";
        if (logoutLink) logoutLink.style.display = "none";
    }
}

function showLogoutLink(show) {
    if (!logoutLink) return;
    logoutLink.style.display = show ? "inline" : "none";
}

onAuthStateChanged(auth, async (user) => {
    console.log("Auth state changed. User:", user);
    if (authControls) {
        authControls.style.visibility = 'visible';
    }
    const siteHeader = document.querySelector('.site-header');

    if (user) {
        if (siteHeader) {
            siteHeader.classList.add('visible');
        }
        if (user.isAnonymous) {
            // Sign out anonymous users and redirect to login page
            await signOut(auth);
            window.location.href = "/login";
            return;
        }
        // User is signed in and not anonymous
        // Get and store the ID token
        try {
            const idToken = await user.getIdToken();
            window.currentUserIdToken = idToken;
            console.log("ID Token obtained and stored");

            // Send user info to backend
            fetch("/api/user-info", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${idToken}`
                },
                body: JSON.stringify({
                    user_id: user.uid,
                    email: user.email
                })
            })
            .then(res => res.json())
            .then(data => console.log("User info response:", data))
            .catch(err => console.error("Error saving user info:", err));
        } catch (error) {
            console.error("Error getting ID token:", error);
            window.currentUserIdToken = null;
        }

        updateUserDisplay(user);
        showLogoutLink(true);

        if (loginTab) {
            loginTab.style.display = "none";
            console.log("Hid loginTab");
        }
        if (registerTab) {
            registerTab.style.display = "none";
            console.log("Hid registerTab");
        }
        setupLogoutHandler();
    } else {
        if (siteHeader) {
            siteHeader.classList.remove('visible');
        }
        console.log("No user logged in or user signed out.");
        // User is signed out
        updateUserDisplay(null);
        showLogoutLink(false);

        if (loginTab) {
            loginTab.style.display = "inline";
            console.log("Displayed loginTab");
        }
        if (registerTab) {
            registerTab.style.display = "inline";
            console.log("Displayed registerTab");
        }
    }
});

// Redirect to login if trying to access bookTracking without authentication and only allow registered users
document.getElementById('bookTrackingTab').addEventListener('click', async (e) => {
    e.preventDefault();
    const user = auth.currentUser;
    if (!user) {
        window.location.href = '/login';
        return;
    }
    // Check if user is anonymous (not registered)
    if (user.isAnonymous) {
        alert("Please register or login to access Book Tracking.");
        window.location.href = '/login';
        return;
    }
    // User is authenticated and registered
    window.location.href = '/bookTracking';
});
