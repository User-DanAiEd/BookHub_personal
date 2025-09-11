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

// Hide auth controls initially until auth state is known
const authControls = document.querySelector('.auth-controls');
if (authControls) {
    authControls.style.visibility = 'hidden';
}

onAuthStateChanged(auth, async (user) => {
    console.log("Auth state changed. User:", user);
    if (authControls) {
        authControls.style.visibility = 'visible';
    }
    const siteHeader = document.querySelector('.site-header');
    const logoutLink = document.getElementById('logoutLink');
    if (user) {
        if (siteHeader) {
            siteHeader.classList.add('visible');
        }
        if (user.email) {
            console.log(`User logged in: ${user.email}`);
        } else {
            console.error("Error: Logged in user has no email address.");
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
        } catch (error) {
            console.error("Error getting ID token:", error);
            window.currentUserIdToken = null;
        }

        if (userIdDisplay) {
            const displayName = user.email || "User";
            userIdDisplay.textContent = `Hi, ${displayName}`;
            userIdDisplay.style.display = "inline-block";
            console.log("Updated userIdDisplay text and made it visible");
        }
        if (loginTab) {
            loginTab.style.display = "none";
            console.log("Hid loginTab");
        }
        if (registerTab) {
            registerTab.style.display = "none";
            console.log("Hid registerTab");
        }
        if (logoutLink) {
            logoutLink.style.display = "inline";
            logoutLink.addEventListener("click", async () => {
                await signOut(auth);
                window.location.href = "/";
            });
            console.log("Displayed logoutLink and attached click handler");
        }
    } else {
        if (siteHeader) {
            siteHeader.classList.remove('visible');
        }
        console.log("No user logged in or user signed out.");
        // User is signed out
        if (userIdDisplay) {
            userIdDisplay.textContent = "";
            userIdDisplay.style.display = "none";
            console.log("Cleared and hid userIdDisplay");
        }
        if (loginTab) {
            loginTab.style.display = "inline";
            console.log("Displayed loginTab");
        }
        if (registerTab) {
            registerTab.style.display = "inline";
            console.log("Displayed registerTab");
        }
        if (logoutLink) {
            logoutLink.style.display = "none";
            console.log("Hid logoutLink");
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
