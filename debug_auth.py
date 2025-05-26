"""
Debug Authentication Script
- Undersøger eksisterende brugere
- Tester password verification
- Opretter en testbruger hvis nødvendigt
"""

from portal.database import get_db, SessionLocal
from portal.models import User, Organization, Avatar
from portal.auth import pwd_context
import sys

# Opret en database session
db = SessionLocal()

def list_users():
    """Viser alle brugere i databasen"""
    users = db.query(User).all()
    if not users:
        print("FEJL: Ingen brugere fundet i databasen!")
        return False
    
    print(f"Fandt {len(users)} brugere:")
    for user in users:
        print(f"  - ID: {user.id}, Navn: {user.name}, E-mail: {user.email}")
    return users

def test_password_verification(email, password):
    """Tester om et password kan verificeres for en bestemt bruger"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        print(f"FEJL: Ingen bruger fundet med e-mail: {email}")
        return False
    
    if not user.password_hash:
        print(f"FEJL: Bruger {email} har ikke et password_hash!")
        return False
    
    verified = pwd_context.verify(password, user.password_hash)
    if verified:
        print(f"SUCCESS: Password for {email} er verificeret korrekt!")
    else:
        print(f"FEJL: Password for {email} kunne ikke verificeres!")
    
    return verified

def create_test_user(email="test@example.com", password="password123"):
    """Opretter en testbruger med sikker adgangskode"""
    # Tjek om bruger allerede findes
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        print(f"Bruger findes allerede: {email}")
        return existing_user
    
    # Find eller opret en organisation
    org = db.query(Organization).first()
    if not org:
        print("Opretter test organisation...")
        org = Organization(name="MyAvatar Demo", subdomain="demo")
        db.add(org)
        db.commit()
        db.refresh(org)
        
        # Opret standard avatars hvis de ikke findes
        avatar_count = db.query(Avatar).filter(Avatar.organization_id == org.id).count()
        if avatar_count == 0:
            print("Opretter standard avatars...")
            db.add_all([
                Avatar(heygen_avatar_id="b5038ba7bd9b4d94ac6b5c9ea70f8d28", name="Standard", type="seated", organization_id=org.id),
                Avatar(heygen_avatar_id="ba93f97aacb84960a423b01278c8dd77", name="Alternativ", type="standing", organization_id=org.id),
            ])
            db.commit()
    
    # Opret bruger med sikkert hashed password
    print(f"Opretter test bruger: {email} / {password}")
    user = User(
        name="Test User",
        email=email,
        password_hash=pwd_context.hash(password),
        organization_id=org.id,
        is_admin=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"SUCCESS: Test bruger oprettet med ID {user.id}")
    return user

def reset_user_password(email, new_password="password123"):
    """Nulstiller en brugers adgangskode"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        print(f"FEJL: Ingen bruger fundet med e-mail: {email}")
        return False
    
    user.password_hash = pwd_context.hash(new_password)
    db.commit()
    print(f"SUCCESS: Password for {email} er nulstillet til '{new_password}'")
    return True

def main():
    print("\n===== DEBUG AUTHENTICATION =====\n")
    
    # Vis eksisterende brugere
    users = list_users()
    
    if not users:
        print("\nIngen brugere fundet. Opretter testbruger...")
        user = create_test_user()
        print(f"\nDu kan nu logge ind med:\nE-mail: {user.email}\nPassword: password123")
    else:
        # Spørg om hvilken operation der skal udføres
        print("\nVælg en operation:")
        print("1. Opret ny testbruger")
        print("2. Nulstil adgangskode for eksisterende bruger")
        print("3. Test adgangskode-verifikation")
        
        choice = input("\nVælg handling (1-3): ")
        
        if choice == "1":
            email = input("E-mail for ny bruger (eller tryk Enter for at bruge test@example.com): ")
            password = input("Adgangskode (eller tryk Enter for at bruge password123): ")
            
            email = email or "test@example.com"
            password = password or "password123"
            
            create_test_user(email, password)
            
        elif choice == "2":
            email = input("E-mail for bruger der skal nulstilles: ")
            password = input("Ny adgangskode (eller tryk Enter for at bruge password123): ")
            
            password = password or "password123"
            
            reset_user_password(email, password)
            
        elif choice == "3":
            email = input("E-mail: ")
            password = input("Adgangskode: ")
            
            test_password_verification(email, password)
            
        else:
            print("Ugyldigt valg!")
    
    print("\n===== DEBUG AFSLUTTET =====\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FEJL: {e}")
    finally:
        db.close()