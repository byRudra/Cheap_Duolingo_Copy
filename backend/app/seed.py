"""Seed the demo course and learners (§7).

    python -m app.seed           # seed only if the database is empty
    python -m app.seed --reset   # drop everything and reseed

Both forms are idempotent. Dates are relative to "today" in APP_TIMEZONE at
the moment the seed runs, so re-seed before a demo to keep the streak alive.
"""

import argparse
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import local_date, utc_now
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import (
    Achievement,
    Course,
    DailyActivity,
    Exercise,
    ExerciseType,
    Lesson,
    Skill,
    Unit,
    User,
    UserAchievement,
    UserLessonProgress,
    UserSkillProgress,
)

Ex = dict[str, Any]


# ── Exercise builders ────────────────────────────────────────────────────────


def mc(prompt: str, options: list[str], answer: str, explanation: str) -> Ex:
    assert answer in options, (prompt, answer)
    return {
        "type": ExerciseType.MULTIPLE_CHOICE,
        "prompt": prompt,
        "payload": {"options": options},
        "solution": {"answer": answer},
        "explanation": explanation,
    }


def wb(prompt: str, tiles: list[str], accepted: list[str], explanation: str) -> Ex:
    return {
        "type": ExerciseType.WORD_BANK,
        "prompt": prompt,
        "payload": {"tiles": tiles},
        "solution": {"accepted": accepted},
        "explanation": explanation,
    }


def mp(pairs: list[tuple[str, str]], explanation: str) -> Ex:
    return {
        "type": ExerciseType.MATCH_PAIRS,
        "prompt": "Match the pairs",
        "payload": {"pairs": [{"left": left, "right": right} for left, right in pairs]},
        "solution": None,
        "explanation": explanation,
    }


def fb(prompt: str, sentence: str, options: list[str], answer: str, explanation: str) -> Ex:
    assert sentence.count("___") == 1 and answer in options, (prompt, sentence)
    return {
        "type": ExerciseType.FILL_BLANK,
        "prompt": prompt,
        "payload": {"sentence": sentence, "options": options},
        "solution": {"answer": answer},
        "explanation": explanation,
    }


def ta(prompt: str, accepted: list[str], explanation: str, placeholder: str = "Type in Spanish") -> Ex:
    return {
        "type": ExerciseType.TYPE_ANSWER,
        "prompt": prompt,
        "payload": {"placeholder": placeholder},
        "solution": {"accepted": accepted},
        "explanation": explanation,
    }


# ── Course content ───────────────────────────────────────────────────────────
# Unit → skills → lessons → exercises. Every lesson uses all five types.

COURSE: list[dict[str, Any]] = [
    {
        "title": "Basics",
        "description": "Say hello, introduce yourself and learn everyday words.",
        "color": "#2FB344",
        "skills": [
            {
                "title": "Greetings",
                "icon": "👋",
                "lessons": [
                    (
                        "Hello and goodbye",
                        [
                            mc("Which one means “hello”?", ["Adiós", "Hola", "Gracias", "Por favor"], "Hola",
                               "“Hola” is the most common way to say hello."),
                            mp([("Hola", "Hello"), ("Adiós", "Goodbye"), ("Gracias", "Thank you"),
                                ("Buenas noches", "Good night")],
                               "These four words cover most everyday greetings."),
                            wb("Translate: “Good morning”", ["días", "noches", "Buenos", "tardes"],
                               ["Buenos días", "Buen día"],
                               "“Buenos días” literally means “good days”."),
                            fb("Fill in the blank: “Good afternoon!”", "¡Buenas ___!", ["tardes", "días", "tarde"],
                               "tardes", "“Buenas tardes” is used from noon until evening."),
                            ta("Type this in Spanish: “Goodbye”", ["Adiós", "Chao", "Chau"],
                               "“Adiós” means goodbye; “chao” is a casual alternative."),
                            mc("How do you say “see you later”?",
                               ["Buenas noches", "Mucho gusto", "Hasta luego", "De nada"], "Hasta luego",
                               "“Hasta luego” literally means “until later”."),
                        ],
                    ),
                    (
                        "How are you?",
                        [
                            mc("What does “¿Cómo estás?” mean?",
                               ["What is your name?", "How are you?", "Where are you?", "How old are you?"],
                               "How are you?", "“¿Cómo estás?” is the informal way to ask how someone is."),
                            fb("Fill in the blank: “I'm fine, thank you.”", "Estoy ___, gracias.",
                               ["bueno", "bien", "buenos"], "bien",
                               "Use “bien” (well) with “estar” to say you're fine."),
                            wb("Translate: “Good night, see you tomorrow”",
                               ["hasta", "días", "Buenas", "luego", "mañana", "noches"],
                               ["Buenas noches, hasta mañana"],
                               "“Hasta mañana” means “until tomorrow”."),
                            mp([("Bien", "Well"), ("Mal", "Badly"), ("Muy", "Very"), ("Mañana", "Tomorrow")],
                               "“Muy bien” means “very well”."),
                            ta("Type this in Spanish: “Thank you very much”", ["Muchas gracias"],
                               "“Muchas” agrees with the feminine plural “gracias”."),
                            mc("Someone says “Gracias.” How do you reply?",
                               ["Por favor", "Hola", "De nada", "Lo siento"], "De nada",
                               "“De nada” means “you're welcome”."),
                        ],
                    ),
                ],
            },
            {
                "title": "Introductions",
                "icon": "🙋",
                "lessons": [
                    (
                        "What's your name?",
                        [
                            mc("How do you ask “What is your name?”",
                               ["¿Cómo estás?", "¿Cómo te llamas?", "¿De dónde eres?", "¿Qué tal?"],
                               "¿Cómo te llamas?", "“¿Cómo te llamas?” literally means “How do you call yourself?”"),
                            fb("Fill in the blank: “My name is Ana.”", "Me ___ Ana.", ["llamar", "llamado", "llamo"],
                               "llamo", "With “me” (myself) use “llamo”: me llamo = I call myself."),
                            wb("Translate: “Nice to meet you”", ["gusto", "poco", "Mucho", "nada"],
                               ["Mucho gusto", "Encantado", "Encantada"],
                               "“Mucho gusto” literally means “much pleasure”."),
                            mp([("Yo", "I"), ("Tú", "You"), ("Él", "He"), ("Ella", "She")],
                               "“Tú” and “él” carry accents; “tu” (your) and “el” (the) do not."),
                            ta("Type this in Spanish: “I am a student”", ["Soy estudiante", "Yo soy estudiante", "Soy un estudiante"],
                               "Spanish drops the article with professions: “soy estudiante”."),
                            mc("What does “Soy de México” mean?",
                               ["I live in Mexico", "I like Mexico", "I am from Mexico", "I am going to Mexico"],
                               "I am from Mexico", "“Ser de” + place tells where someone is from."),
                        ],
                    ),
                    (
                        "Where are you from?",
                        [
                            mc("How do you ask “Where are you from?”",
                               ["¿Dónde estás?", "¿De dónde eres?", "¿Adónde vas?", "¿Cómo eres?"],
                               "¿De dónde eres?", "“¿De dónde eres?” uses “ser” for origin."),
                            fb("Fill in the blank: “She is from Spain.”", "Ella ___ de España.", ["eres", "soy", "es"],
                               "es", "“Es” is the form of “ser” for él/ella."),
                            wb("Translate: “I am from India”", ["India", "Estoy", "de", "Soy", "en"],
                               ["Soy de India", "Yo soy de India", "Soy de la India"],
                               "Origin uses “ser”, not “estar”."),
                            mp([("Nosotros", "We"), ("Ellos", "They"), ("Usted", "You (formal)"),
                                ("Ustedes", "You (plural)")],
                               "“Usted” is the polite form of “you”."),
                            ta("Type this in Spanish: “Where are you from?”", ["¿De dónde eres?", "¿De dónde es usted?"],
                               "Questions open with “¿” and “dónde” carries an accent."),
                            mc("Choose the correct translation of “We are friends.”",
                               ["Son amigos", "Soy amigo", "Somos amigos", "Estamos amigos"], "Somos amigos",
                               "“Somos” is the “nosotros” form of “ser”."),
                        ],
                    ),
                ],
            },
            {
                "title": "Common Words",
                "icon": "💬",
                "lessons": [
                    (
                        "Yes, no, please",
                        [
                            mc("Which one means “please”?", ["Gracias", "Perdón", "Por favor", "De nada"], "Por favor",
                               "“Por favor” makes any request polite."),
                            mp([("Sí", "Yes"), ("También", "Also"), ("Siempre", "Always"), ("Nunca", "Never")],
                               "“Sí” (yes) has an accent; “si” (if) does not."),
                            fb("Fill in the blank: “Excuse me, where is the bathroom?”", "Perdón, ¿dónde ___ el baño?",
                               ["es", "está", "estás"], "está",
                               "Use “está” (from “estar”) for where things are."),
                            wb("Translate: “Yes, please”", ["favor", "No", "Sí", "gracias", "por"], ["Sí, por favor"],
                               "Remember the accent on “sí” when it means yes."),
                            ta("Type this in Spanish: “Also”", ["También"], "“También” has an accent on the final “e”."),
                            mc("What does “Lo siento” mean?",
                               ["I'm lost", "I'm sorry", "See you soon", "I understand"], "I'm sorry",
                               "“Lo siento” literally means “I feel it”, used as “I'm sorry”."),
                        ],
                    ),
                    (
                        "Little words",
                        [
                            mc("Which one means “today”?", ["Mañana", "Ayer", "Hoy", "Ahora"], "Hoy",
                               "“Hoy” means today; “mañana” means tomorrow."),
                            fb("Fill in the blank: “I don't understand.”", "Yo no ___.",
                               ["entiende", "entiendo", "entiendes"], "entiendo",
                               "“Entiendo” is the “yo” form of “entender”."),
                            mp([("Hoy", "Today"), ("Ayer", "Yesterday"), ("Ahora", "Now"), ("Aquí", "Here")],
                               "“Aquí” has an accent on the “i”."),
                            wb("Translate: “I speak a little Spanish”",
                               ["español", "de", "poco", "Hablo", "mucho", "un", "inglés"],
                               ["Hablo un poco de español", "Yo hablo un poco de español", "Hablo un poco español"],
                               "“Un poco de” means “a little (of)”."),
                            ta("Type this in Spanish: “Where is the bathroom?”", ["¿Dónde está el baño?"],
                               "“Dónde” and “está” both carry accents."),
                            mc("What does “¿Hablas inglés?” mean?",
                               ["Are you English?", "Do you like English?", "Do you speak English?",
                                "Where is England?"], "Do you speak English?",
                               "“Hablas” is the “tú” form of “hablar” (to speak)."),
                        ],
                    ),
                ],
            },
        ],
    },
    {
        "title": "Food",
        "description": "Order food and drinks and talk about what you like.",
        "color": "#F59E0B",
        "skills": [
            {
                "title": "Food",
                "icon": "🍎",
                "lessons": [
                    (
                        "Fruits and basics",
                        [
                            mc("Which one means “apple”?", ["La naranja", "La manzana", "El pan", "El queso"],
                               "La manzana", "“Manzana” is feminine, so it takes “la”."),
                            mp([("El pan", "Bread"), ("El queso", "Cheese"), ("El arroz", "Rice"), ("El huevo", "Egg")],
                               "All four of these nouns are masculine."),
                            fb("Fill in the blank: “I eat an apple.”", "Yo ___ una manzana.", ["comes", "como", "come"],
                               "como", "“Como” is the “yo” form of “comer” (to eat)."),
                            wb("Translate: “The bread is good”", ["bueno", "pan", "La", "es", "El", "buena"],
                               ["El pan es bueno", "El pan está bueno"],
                               "“Pan” is masculine, so the adjective is “bueno”."),
                            ta("Type this in Spanish: “the cheese”", ["El queso", "Queso"],
                               "“Queso” is masculine: “el queso”."),
                            mc("What does “Me gusta la fruta” mean?",
                               ["I want fruit", "I buy fruit", "I like fruit", "I have fruit"], "I like fruit",
                               "“Me gusta” literally means “it pleases me”."),
                        ],
                    ),
                    (
                        "I'm hungry",
                        [
                            mc("How do you say “I'm hungry”?",
                               ["Tengo sed", "Tengo hambre", "Estoy cansado", "Tengo frío"], "Tengo hambre",
                               "Spanish says “I have hunger”: tengo hambre."),
                            fb("Fill in the blank: “The apples are red.”", "Las manzanas son ___.",
                               ["rojo", "roja", "rojas"], "rojas",
                               "Adjectives agree in gender and number: manzanas → rojas."),
                            mp([("La carne", "Meat"), ("El pollo", "Chicken"), ("El pescado", "Fish"),
                                ("La ensalada", "Salad")],
                               "“Pescado” is fish as food; a live fish is “pez”."),
                            wb("Translate: “We eat rice and chicken”",
                               ["pollo", "Comemos", "y", "pescado", "arroz", "como"],
                               ["Comemos arroz y pollo", "Nosotros comemos arroz y pollo"],
                               "“Comemos” is the “nosotros” form of “comer”."),
                            ta("Type this in Spanish: “I like chicken”", ["Me gusta el pollo"],
                               "Spanish keeps the article: me gusta el pollo."),
                            mc("What does “La sopa está caliente” mean?",
                               ["The soup is cold", "The soup is hot", "The soup is good", "The soup is ready"],
                               "The soup is hot", "“Caliente” means hot (temperature)."),
                        ],
                    ),
                ],
            },
            {
                "title": "Drinks",
                "icon": "🥤",
                "lessons": [
                    (
                        "Water, please",
                        [
                            mc("Which one means “water”?", ["La leche", "El jugo", "El agua", "El café"], "El agua",
                               "“Agua” is feminine but takes “el” because it starts with a stressed “a”."),
                            mp([("El café", "Coffee"), ("El té", "Tea"), ("La leche", "Milk"), ("El jugo", "Juice")],
                               "“Té” (tea) has an accent; “te” (you) does not."),
                            fb("Fill in the blank: “I drink coffee.”", "Yo ___ café.", ["bebe", "bebes", "bebo"],
                               "bebo", "“Bebo” is the “yo” form of “beber” (to drink)."),
                            wb("Translate: “Water, please”", ["por", "leche", "Agua", "favor", "gracias"],
                               ["Agua, por favor", "Un agua, por favor"],
                               "Add “por favor” to make it polite."),
                            ta("Type this in Spanish: “I'm thirsty”", ["Tengo sed", "Yo tengo sed"],
                               "Like hunger, thirst uses “tener”: tengo sed."),
                            mc("What does “¿Quieres un té?” mean?",
                               ["Do you have tea?", "Is the tea hot?", "Do you like tea?", "Do you want a tea?"],
                               "Do you want a tea?", "“Quieres” is the “tú” form of “querer” (to want)."),
                        ],
                    ),
                    (
                        "Hot and cold",
                        [
                            mc("How do you say “cold water”?", ["Agua frío", "Agua fría", "Fría agua", "Agua caliente"],
                               "Agua fría", "“Agua” is feminine, so the adjective is “fría” (even with “el agua”)."),
                            fb("Fill in the blank: “The coffee is hot.”", "El café está ___.",
                               ["caliente", "fría", "calientes"], "caliente", "“Caliente” is the same for both genders."),
                            mp([("Caliente", "Hot"), ("Frío", "Cold"), ("Dulce", "Sweet"), ("El vaso", "Glass")],
                               "“Vaso” is a drinking glass; “vidrio” is the material."),
                            wb("Translate: “I want a glass of milk”",
                               ["vaso", "leche", "una", "Quiero", "de", "agua", "un"],
                               ["Quiero un vaso de leche", "Yo quiero un vaso de leche"],
                               "“Un vaso de leche” = a glass of milk."),
                            ta("Type this in Spanish: “Orange juice”", ["Jugo de naranja", "Zumo de naranja"],
                               "“Jugo” is used in Latin America; “zumo” in Spain."),
                            mc("What is “el vino”?", ["Vinegar", "Wine", "Water", "Beer"], "Wine",
                               "“Vino” means wine; vinegar is “vinagre”."),
                        ],
                    ),
                ],
            },
            {
                "title": "Restaurants",
                "icon": "🍽️",
                "lessons": [
                    (
                        "Ordering",
                        [
                            mc("How do you ask for the menu?",
                               ["La cuenta, por favor", "El menú, por favor", "Una mesa, por favor",
                                "El baño, por favor"], "El menú, por favor",
                               "In Spain you'll also hear “la carta”."),
                            fb("Fill in the blank: “I would like a table for two.”", "Quisiera una ___ para dos.",
                               ["mesas", "mesa", "mesero"], "mesa", "“Quisiera” is a polite “I would like”."),
                            mp([("La mesa", "Table"), ("La cuenta", "Bill"), ("El camarero", "Waiter"),
                                ("El menú", "Menu")],
                               "“Camarero” is common in Spain; “mesero” in Mexico."),
                            wb("Translate: “The bill, please”", ["favor", "cuenta", "El", "por", "mesa", "La"],
                               ["La cuenta, por favor"], "“Cuenta” is feminine: la cuenta."),
                            ta("Type this in Spanish: “A table for two, please”",
                               ["Una mesa para dos, por favor", "Mesa para dos, por favor"],
                               "“Para dos” means “for two”."),
                            mc("The waiter asks “¿Qué desea?” What does it mean?",
                               ["Where do you want to sit?", "What would you like?", "Are you ready?", "How was it?"],
                               "What would you like?", "“Desear” means to wish or want; it's a polite question."),
                        ],
                    ),
                    (
                        "At the table",
                        [
                            mc("Which one means “delicious”?", ["Caliente", "Barato", "Delicioso", "Lleno"], "Delicioso",
                               "“Delicioso” changes to “deliciosa” for feminine nouns."),
                            fb("Fill in the blank: “The food is delicious.”", "La comida está ___.",
                               ["delicioso", "deliciosa", "deliciosos"], "deliciosa",
                               "“Comida” is feminine singular, so “deliciosa”."),
                            mp([("El tenedor", "Fork"), ("El cuchillo", "Knife"), ("La cuchara", "Spoon"),
                                ("El plato", "Plate")],
                               "“Cuchara” (spoon) and “cuchillo” (knife) are easy to mix up."),
                            wb("Translate: “I want the fish, please”",
                               ["pescado", "el", "Quiero", "favor", "pollo", "por", "la"],
                               ["Quiero el pescado, por favor", "Yo quiero el pescado, por favor"],
                               "“Pescado” is masculine: el pescado."),
                            ta("Type this in Spanish: “Water without ice”", ["Agua sin hielo"],
                               "“Sin” means without; “hielo” means ice."),
                            mc("What does “¿Está incluida la propina?” mean?",
                               ["Is the table free?", "Is the kitchen open?", "Is the tip included?",
                                "Is dessert included?"], "Is the tip included?", "“La propina” is the tip."),
                        ],
                    ),
                ],
            },
        ],
    },
    {
        "title": "Everyday Life",
        "description": "Talk about family, your day and getting around town.",
        "color": "#8B5CF6",
        "skills": [
            {
                "title": "Family",
                "icon": "👪",
                "lessons": [
                    (
                        "My family",
                        [
                            mc("Which one means “mother”?", ["El padre", "La hermana", "La madre", "La abuela"],
                               "La madre", "“Madre” is mother; “mamá” is mom."),
                            mp([("El padre", "Father"), ("La madre", "Mother"), ("El hermano", "Brother"),
                                ("La hermana", "Sister")],
                               "Masculine family words usually end in -o, feminine in -a."),
                            fb("Fill in the blank: “My brothers are tall.”", "Mis hermanos son ___.",
                               ["alto", "altos", "altas"], "altos",
                               "“Hermanos” is masculine plural, so “altos”."),
                            wb("Translate: “This is my sister”", ["hermana", "Este", "mi", "es", "hermano", "Esta"],
                               ["Esta es mi hermana"], "“Esta” agrees with the feminine “hermana”."),
                            ta("Type this in Spanish: “my family”", ["Mi familia"],
                               "“Mi” (my) has no accent; “mí” (me) does."),
                            mc("What does “Tengo dos hermanos” mean?",
                               ["I have two sons", "I have two brothers", "I have two friends", "I am two brothers"],
                               "I have two brothers", "“Hermanos” can also mean siblings in general."),
                        ],
                    ),
                    (
                        "Grandparents and kids",
                        [
                            mc("Which one means “grandfather”?", ["El tío", "El primo", "El abuelo", "El hijo"],
                               "El abuelo", "“Abuelo” is grandfather; “abuela” is grandmother."),
                            fb("Fill in the blank: “My grandmother has a cat.”", "Mi abuela ___ un gato.",
                               ["tengo", "tiene", "tienes"], "tiene",
                               "“Tiene” is the “él/ella” form of “tener”."),
                            mp([("El hijo", "Son"), ("La hija", "Daughter"), ("El tío", "Uncle"), ("La tía", "Aunt")],
                               "Change -o to -a for the feminine form."),
                            wb("Translate: “Our grandparents live in Madrid”",
                               ["abuelos", "vive", "Nuestros", "en", "Madrid", "viven", "Nuestras"],
                               ["Nuestros abuelos viven en Madrid"],
                               "“Abuelos” is masculine plural, so “nuestros” and “viven”."),
                            ta("Type this in Spanish: “The children are happy”",
                               ["Los niños están felices", "Los niños son felices", "Los niños están contentos"],
                               "“Niños” has an “ñ”, and “están” carries an accent."),
                            mc("How do you say “my parents”?",
                               ["Mi padres", "Mis parientes", "Mis padres", "Mis padre"], "Mis padres",
                               "“Padres” means parents; “parientes” means relatives."),
                        ],
                    ),
                ],
            },
            {
                "title": "Daily Routine",
                "icon": "⏰",
                "lessons": [
                    (
                        "Mornings",
                        [
                            mc("Which one means “I wake up”?", ["Me acuesto", "Me despierto", "Me ducho", "Me visto"],
                               "Me despierto", "“Despertarse” is a reflexive verb: me despierto."),
                            fb("Fill in the blank: “I get up at seven.”", "Me levanto a las ___.",
                               ["siente", "siete", "séptimo"], "siete",
                               "“Siete” is seven; “siente” means he/she feels."),
                            mp([("La mañana", "Morning"), ("La tarde", "Afternoon"), ("La noche", "Night"),
                                ("El día", "Day")],
                               "“Día” is masculine even though it ends in -a."),
                            wb("Translate: “I take a shower every morning”",
                               ["mañana", "Me", "noche", "cada", "ducho", "baño"],
                               ["Me ducho cada mañana", "Me ducho todas las mañanas", "Me baño cada mañana"],
                               "“Cada” means each or every."),
                            ta("Type this in Spanish: “I eat breakfast”", ["Desayuno", "Yo desayuno"],
                               "“Desayunar” means to have breakfast."),
                            mc("What does “¿Qué hora es?” mean?",
                               ["How many hours?", "What day is it?", "What time is it?", "When is it?"],
                               "What time is it?", "Ask the time with “¿Qué hora es?”"),
                        ],
                    ),
                    (
                        "Evenings",
                        [
                            mc("Which one means “I go to bed”?", ["Me levanto", "Me lavo", "Me despierto", "Me acuesto"],
                               "Me acuesto", "“Acostarse” means to go to bed."),
                            fb("Fill in the blank: “We have dinner at nine.”", "Nosotros ___ a las nueve.",
                               ["cenan", "cenamos", "ceno"], "cenamos",
                               "“Cenamos” is the “nosotros” form of “cenar”."),
                            mp([("Desayunar", "To have breakfast"), ("Almorzar", "To have lunch"),
                                ("Cenar", "To have dinner"), ("Dormir", "To sleep")],
                               "Spanish has a single verb for each meal."),
                            wb("Translate: “I read a book at night”",
                               ["libro", "un", "día", "Leo", "noche", "la", "por", "Lee"],
                               ["Leo un libro por la noche", "Por la noche leo un libro",
                                "Yo leo un libro por la noche"],
                               "“Por la noche” means at night."),
                            ta("Type this in Spanish: “I'm tired”", ["Estoy cansado", "Estoy cansada"],
                               "Use “cansado” if you're male and “cansada” if you're female."),
                            mc("What does “Son las diez” mean?",
                               ["They are ten", "It's ten o'clock", "It's ten minutes", "At ten"], "It's ten o'clock",
                               "Times use “son las” (except one o'clock: “es la una”)."),
                        ],
                    ),
                ],
            },
            {
                "title": "Places",
                "icon": "🏙️",
                "lessons": [
                    (
                        "Around town",
                        [
                            mc("Which one means “the library”?",
                               ["La librería", "La biblioteca", "El libro", "La escuela"], "La biblioteca",
                               "False friend: “librería” is a bookshop."),
                            mp([("El mercado", "Market"), ("La playa", "Beach"), ("El parque", "Park"),
                                ("La ciudad", "City")],
                               "Nouns ending in -dad, like “ciudad”, are feminine."),
                            fb("Fill in the blank: “The bank is near here.”", "El banco está ___ de aquí.",
                               ["cercana", "cerca", "cerco"], "cerca", "“Cerca de” means near; “lejos de” means far from."),
                            wb("Translate: “Where is the station?”", ["la", "es", "estación", "Dónde", "el", "está"],
                               ["¿Dónde está la estación?"], "Use “estar” for location: ¿dónde está…?"),
                            ta("Type this in Spanish: “the beach”", ["La playa", "Playa"],
                               "“Playa” is feminine: la playa."),
                            mc("What does “Voy al mercado” mean?",
                               ["I'm at the market", "I like the market", "I'm going to the market",
                                "I sell at the market"], "I'm going to the market",
                               "“Al” is “a + el”: voy al mercado."),
                        ],
                    ),
                    (
                        "Directions",
                        [
                            mc("Which one means “to the left”?",
                               ["A la derecha", "Todo recto", "A la izquierda", "Al lado"], "A la izquierda",
                               "“Izquierda” is left; “derecha” is right."),
                            fb("Fill in the blank: “Turn right.”", "Gira a la ___.", ["derechas", "derecha", "derecho"],
                               "derecha", "“A la derecha” means to the right."),
                            mp([("Izquierda", "Left"), ("Derecha", "Right"), ("Cerca", "Near"), ("Lejos", "Far")],
                               "Pair opposites to remember them."),
                            wb("Translate: “The museum is far from the hotel”",
                               ["museo", "lejos", "El", "cerca", "del", "está", "hotel", "es"],
                               ["El museo está lejos del hotel"], "“Del” is “de + el”."),
                            ta("Type this in Spanish: “Where is the hotel?”", ["¿Dónde está el hotel?"],
                               "The “h” in “hotel” is silent in Spanish."),
                            mc("What does “Sigue todo recto” mean?",
                               ["Turn around", "Go straight ahead", "Stop here", "Take the second left"],
                               "Go straight ahead", "“Todo recto” means straight ahead."),
                        ],
                    ),
                ],
            },
        ],
    },
]

ACHIEVEMENTS = [
    ("FIRST_LESSON", "First Steps", "Complete your first lesson.", "🏆"),
    ("PERFECT_LESSON", "Flawless", "Complete a lesson with no mistakes.", "🎯"),
    ("XP_100", "XP Hunter", "Earn 100 total XP.", "⭐"),
    ("STREAK_3", "On Fire", "Reach a 3-day streak.", "🔥"),
    ("LESSONS_5", "Dedicated", "Complete 5 different lessons.", "📚"),
]

LEADERBOARD_RIVALS = [
    ("sofia", "Sofía", "#EC4899", 140),
    ("mateo", "Mateo", "#0EA5E9", 95),
    ("priya", "Priya", "#F97316", 70),
    ("liam", "Liam", "#14B8A6", 38),
    ("aisha", "Aisha", "#A855F7", 20),
]


def _utc_at_local_noon(day, tz_name: str) -> datetime:
    """Naive-UTC timestamp for midday on ``day`` in the app timezone."""
    local = datetime.combine(day, time(12, 0), tzinfo=ZoneInfo(tz_name))
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def is_seeded(db: Session) -> bool:
    return db.scalars(select(Course.id)).first() is not None


def seed(db: Session, now: datetime | None = None) -> None:
    now = now or utc_now()
    today = local_date(now)
    tz = settings.APP_TIMEZONE

    # Course content
    course = Course(title="Spanish", language_code="es", flag_emoji="🇪🇸")
    db.add(course)
    skill_order = 0
    all_skills: list[Skill] = []
    for unit_index, unit_data in enumerate(COURSE, start=1):
        unit = Unit(
            course=course,
            order_index=unit_index,
            title=unit_data["title"],
            description=unit_data["description"],
            color=unit_data["color"],
        )
        db.add(unit)
        for skill_data in unit_data["skills"]:
            skill_order += 1
            skill = Skill(unit=unit, order_index=skill_order, title=skill_data["title"], icon=skill_data["icon"])
            db.add(skill)
            all_skills.append(skill)
            for lesson_index, (lesson_title, exercises) in enumerate(skill_data["lessons"], start=1):
                lesson = Lesson(skill=skill, order_index=lesson_index, title=lesson_title)
                db.add(lesson)
                for ex_index, ex in enumerate(exercises, start=1):
                    db.add(Exercise(lesson=lesson, order_index=ex_index, **ex))

    achievements = {code: Achievement(code=code, title=title, description=desc, icon=icon)
                    for code, title, desc, icon in ACHIEVEMENTS}
    db.add_all(achievements.values())
    db.flush()

    # Demo learner: Greetings done, Introductions half done, 3-day streak ending yesterday.
    day = [today - timedelta(days=offset) for offset in (3, 2, 1)]
    arnav = User(
        username=settings.DEMO_USERNAME,
        display_name="Arnav",
        avatar_color="#22C55E",
        xp=45,
        gems=500,
        hearts=settings.MAX_HEARTS,
        hearts_updated_at=now,
        streak=3,
        longest_streak=3,
        last_activity_date=day[2],
        daily_goal_xp=settings.DEFAULT_DAILY_GOAL_XP,
        created_at=_utc_at_local_noon(today - timedelta(days=10), tz),
    )
    db.add(arnav)
    db.flush()

    greetings, introductions = all_skills[0], all_skills[1]
    completed = [(greetings.lessons[0], day[0]), (greetings.lessons[1], day[1]),
                 (introductions.lessons[0], day[2])]
    for lesson, when in completed:
        # One mistake each: consistent with PERFECT_LESSON still being locked.
        db.add(UserLessonProgress(user_id=arnav.id, lesson_id=lesson.id,
                                  completed_at=_utc_at_local_noon(when, tz), best_mistakes=1))
    db.add(UserSkillProgress(user_id=arnav.id, skill_id=greetings.id,
                             unlocked_at=_utc_at_local_noon(day[0], tz), lessons_completed=2))
    db.add(UserSkillProgress(user_id=arnav.id, skill_id=introductions.id,
                             unlocked_at=_utc_at_local_noon(day[1], tz), lessons_completed=1))
    # 45 XP = three first completions (10 each) + three practice replays (5 each).
    for when in day:
        db.add(DailyActivity(user_id=arnav.id, date=when, xp_earned=15, lessons_completed=2))
    db.add(UserAchievement(user_id=arnav.id, achievement_id=achievements["FIRST_LESSON"].id,
                           unlocked_at=_utc_at_local_noon(day[0], tz)))
    db.add(UserAchievement(user_id=arnav.id, achievement_id=achievements["STREAK_3"].id,
                           unlocked_at=_utc_at_local_noon(day[2], tz)))

    for username, name, color, xp in LEADERBOARD_RIVALS:
        db.add(User(username=username, display_name=name, avatar_color=color, xp=xp, gems=500,
                    hearts=settings.MAX_HEARTS, hearts_updated_at=now, streak=0, longest_streak=0,
                    last_activity_date=None, daily_goal_xp=settings.DEFAULT_DAILY_GOAL_XP,
                    created_at=_utc_at_local_noon(today - timedelta(days=30), tz)))

    db.commit()


def reset_database() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Habla demo database.")
    parser.add_argument("--reset", action="store_true", help="drop all tables and reseed")
    args = parser.parse_args()

    if args.reset:
        reset_database()
    else:
        Base.metadata.create_all(engine)

    with SessionLocal() as db:
        if is_seeded(db):
            print("Database already seeded; nothing to do (use --reset to start over).")
            return
        seed(db)
        exercises = db.query(Exercise).count()
        print(f"Seeded Spanish course: {len(COURSE)} units, 9 skills, {exercises} exercises; "
              f"learner '{settings.DEMO_USERNAME}' + {len(LEADERBOARD_RIVALS)} rivals.")


if __name__ == "__main__":
    main()
