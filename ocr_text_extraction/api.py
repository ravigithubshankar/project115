"""
from pymongo import MongoClient, ASCENDING, UpdateOne
from datetime import datetime
import logging
import random

# MongoDB connection
uri = "mongodb://localhost:27017"
client = MongoClient(uri)
db = client["answer"]
answers_collection = db["answers"]
questions_collection = db["questions"]

# Configure logging to show full messages
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

# List of random questions for fallback
RANDOM_QUESTIONS = [
    "What is the difference between AI and machine learning?",
    "How does a neural network function?",
    "What are the applications of reinforcement learning?",
    "What is the role of activation functions in deep learning?",
    "How can overfitting be prevented in machine learning models?"
]

# Drop incorrect index and create the correct compound index
try:
    print("Connected to MongoDB")
    # Check current indexes
    print("Current indexes:", answers_collection.index_information())
    
    # Drop the incorrect roll_no_1_question_id_1 index if it exists
    try:
        answers_collection.drop_index("roll_no_1_question_id_1")
        print("Dropped index: roll_no_1_question_id_1")
    except Exception as e:
        print(f"Index roll_no_1_question_id_1 not found or error dropping: {e}")
    
    # Drop the existing roll_no_1_questionId_1 index to recreate it
    try:
        answers_collection.drop_index("roll_no_1_questionId_1")
        print("Dropped index: roll_no_1_questionId_1")
    except Exception as e:
        print(f"Index roll_no_1_questionId_1 not found or error dropping: {e}")
    
    # Create the correct compound unique index on roll_no and questionId
    answers_collection.create_index([("roll_no", ASCENDING), ("questionId", ASCENDING)], unique=True)
    print("Compound index created successfully")
    
    # Verify the new index
    print("Indexes after update:", answers_collection.index_information())
except Exception as e:
    print(f"Error managing indexes: {e}")

# Update schema validation for answers collection
try:
    db.command({
        "collMod": "answers",
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["roll_no", "questionId", "question_text", "answer_text", "created_at", "updated_at"],
                "properties": {
                    "_id": {"bsonType": "objectId"},
                    "roll_no": {"bsonType": "string"},
                    "questionId": {"bsonType": "string"},
                    "question_text": {"bsonType": ["string", "null"]},
                    "answer_text": {"bsonType": "string"},
                    "created_at": {"bsonType": "date"},
                    "updated_at": {"bsonType": "date"}
                },
                "additionalProperties": False
            }
        },
        "validationLevel": "strict",
        "validationAction": "error"
    })
    print("Schema validation updated successfully")
except Exception as e:
    print(f"Error updating schema validation: {e}")

# Clean up existing documents to align with the new questionId format
try:
    # Inspect documents with roll_no: "211FA18115"
    docs = answers_collection.find({"roll_no": "211FA18115"})
    print("Documents with roll_no '211FA18115' in answers collection:")
    for doc in docs:
        print(doc)

    # Update existing questionId values from Q1 to QQ1, Q2 to QQ2, etc.
    docs = answers_collection.find({"roll_no": "211FA18115"})
    for doc in docs:
        if "questionId" in doc and isinstance(doc["questionId"], str) and doc["questionId"].startswith("Q"):
            # Extract the number part (e.g., "1" from "Q1")
            number_part = doc["questionId"][1:] if doc["questionId"].startswith("QQ") else doc["questionId"][1:]
            new_question_id = f"QQ{number_part}"
            answers_collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"questionId": new_question_id}}
            )
    print("Updated existing questionId to use QQ prefix")

    # Convert any integer questionId to string format (e.g., 1 to "QQ1")
    docs = answers_collection.find({"roll_no": "211FA18115"})
    for doc in docs:
        if "questionId" in doc and isinstance(doc["questionId"], int):
            new_question_id = f"QQ{doc['questionId']}"
            answers_collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"questionId": new_question_id}}
            )
    print("Converted existing integer questionId to string format with QQ prefix")

    # Delete documents with question_id: null
    result = answers_collection.delete_many({"question_id": None})
    print(f"Deleted {result.deleted_count} documents with question_id: null")

    # Rename question_id to questionId if it exists in any documents
    rename_result = answers_collection.update_many(
        {"question_id": {"$exists": True}},
        {"$rename": {"question_id": "questionId"}}
    )
    print(f"Renamed question_id to questionId in {rename_result.modified_count} documents")
except Exception as e:
    print(f"Error inspecting or cleaning documents: {e}")

def store_in_db(student_data):
    try:
        # Validate input structure
        if not isinstance(student_data, dict):
            raise ValueError("student_data must be a dictionary")
        required_fields = ["roll_no", "created_at", "updated_at", "answers"]
        for field in required_fields:
            if field not in student_data:
                raise ValueError(f"Missing required field: {field}")
        if not isinstance(student_data["answers"], list):
            raise ValueError("answers must be a list")

        roll_no = student_data["roll_no"]
        created_at = datetime.fromisoformat(student_data["created_at"])
        updated_at = datetime.fromisoformat(student_data["updated_at"])
        answers = student_data["answers"]

        logging.debug(f"Full student_data: {student_data}")
        logging.debug(f"Answers array: {answers}")

        operations = []
        skipped = 0

        for i, ans in enumerate(answers):
            question_no = ans.get("question_no")
            answer_text = ans.get("answer_text")

            logging.debug(f"Answer {i}: question_no={question_no}, answer_text={answer_text}")

            # Skip if question_no is None, not an integer, or answer_text is None
            if question_no is None or not isinstance(question_no, int) or answer_text is None:
                skipped += 1
                logging.warning(f"Skipped answer {i}: question_no={question_no}, answer_text={answer_text}")
                continue

            # Map question_no (integer) to questionId (string, e.g., "QQ1")
            question_id_str = f"QQ{question_no}"

            # Fetch the actual question_text from the questions collection
            question_doc = questions_collection.find_one({"questionId": question_id_str})
            if not question_doc:
                logging.warning(f"No question found for questionId={question_id_str}, using random question")
                question_text = random.choice(RANDOM_QUESTIONS)
            else:
                question_text = question_doc.get("question", random.choice(RANDOM_QUESTIONS))

            operations.append(UpdateOne(
                {"roll_no": roll_no, "questionId": question_id_str},
                {
                    "$set": {
                        "question_text": question_text,
                        "answer_text": answer_text,
                        "updated_at": updated_at
                    },
                    "$setOnInsert": {
                        "created_at": created_at
                    }
                },
                upsert=True
            ))

        if operations:
            logging.debug(f"Executing bulk write with {len(operations)} operations")
            result = answers_collection.bulk_write(operations)

            # After bulk write, restructure the documents to enforce field order
            docs = answers_collection.find({"roll_no": roll_no})
            for doc in docs:
                # Create a new document with the desired field order
                new_doc = {
                    "_id": doc["_id"],
                    "roll_no": doc["roll_no"],
                    "questionId": doc["questionId"],
                    "question_text": doc["question_text"],
                    "answer_text": doc["answer_text"],
                    "created_at": doc["created_at"],
                    "updated_at": doc["updated_at"]
                }
                # Replace the old document with the new one
                answers_collection.replace_one({"_id": doc["_id"]}, new_doc)

            return {
                "message": "Data stored successfully",
                "matched_count": result.matched_count,
                "modified_count": result.modified_count,
                "upserted_count": len(result.upserted_ids),
                "skipped_entries": skipped
            }
        else:
            return {
                "message": "No operations performed",
                "matched_count": 0,
                "skipped_entries": skipped
            }

    except Exception as e:
        logging.error(f"Failed to store data: {str(e)}")
        raise Exception(f"Failed to store data: {str(e)}")

def close_connection():
    client.close()
    print("MongoDB connection closed")

# Test the function
if __name__ == "__main__":
    student_data = {
        "roll_no": "211FA18115",
        "created_at": "2025-06-09T20:03:02.069Z",
        "updated_at": "2025-06-09T20:03:02.069Z",
        "answers": [
            {
                "question_no": 1,
                "question_text": None,
                "answer_text": "Machine learning (ML) is a subset of artificial intelligence (AI) that allows systems to learn from data and improve their performance on tasks over time without being explicitly programmed."
            },
            {
                "question_no": 2,
                "question_text": None,
                "answer_text": "Classification predicts discrete labels in categories (e.g., spam & not spam). Regression predicts continuous values (e.g., house price prediction)."
            },
            {
                "question_no": 3,
                "question_text": None,
                "answer_text": "Overfitting: The model learns the training data too well, but performs too bad on unseen data, leading to high variance and less bias. Underfitting: The model learns the training data to poor can't capture the patterns in both training data and testing data, leading to high bias and less variance."
            }
        ]
    }
    try:
        result = store_in_db(student_data)
        print(result)
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        close_connection()
"""



from pymongo import MongoClient, ASCENDING, UpdateOne
from datetime import datetime
import logging

# MongoDB connection
uri = "mongodb://localhost:27017"
client = MongoClient(uri)
db = client["answer"]
answers_collection = db["answers"]
questions_collection = db["questions"]

# Configure logging to show full messages
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

# Drop incorrect index and create the correct compound index
try:
    print("Connected to MongoDB")
    # Check current indexes
    print("Current indexes:", answers_collection.index_information())
    
    # Drop the incorrect roll_no_1_question_id_1 index if it exists
    try:
        answers_collection.drop_index("roll_no_1_question_id_1")
        print("Dropped index: roll_no_1_question_id_1")
    except Exception as e:
        print(f"Index roll_no_1_question_id_1 not found or error dropping: {e}")
    
    # Drop the existing roll_no_1_questionId_1 index to recreate it with the updated field type
    try:
        answers_collection.drop_index("roll_no_1_questionId_1")
        print("Dropped index: roll_no_1_questionId_1")
    except Exception as e:
        print(f"Index roll_no_1_questionId_1 not found or error dropping: {e}")
    
    # Create the correct compound unique index on roll_no and questionId (now as string)
    answers_collection.create_index([("roll_no", ASCENDING), ("questionId", ASCENDING)], unique=True)
    print("Compound index created successfully")
    
    # Verify the new index
    print("Indexes after update:", answers_collection.index_information())
except Exception as e:
    print(f"Error managing indexes: {e}")

# Update schema validation for answers collection
try:
    db.command({
        "collMod": "answers",
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["roll_no", "questionId", "question_text", "answer_text", "created_at", "updated_at"],
                "properties": {
                    "_id": {"bsonType": "objectId"},
                    "roll_no": {"bsonType": "string"},
                    "questionId": {"bsonType": "string"},  # Changed to string
                    "question_text": {"bsonType": ["string", "null"]},
                    "answer_text": {"bsonType": "string"},
                    "created_at": {"bsonType": "date"},
                    "updated_at": {"bsonType": "date"}
                },
                "additionalProperties": False
            }
        },
        "validationLevel": "strict",
        "validationAction": "error"
    })
    print("Schema validation updated successfully")
except Exception as e:
    print(f"Error updating schema validation: {e}")

# Clean up existing documents to align with the new string questionId format
try:
    # Inspect documents with roll_no: "211FA18115"
    docs = answers_collection.find({"roll_no": "211FA18115"})
    print("Documents with roll_no '211FA18115' in answers collection:")
    for doc in docs:
        print(doc)

    # Convert existing integer questionId to string format (e.g., 1 to "Q1")
    docs = answers_collection.find({"roll_no": "211FA18115"})
    for doc in docs:
        if "questionId" in doc and isinstance(doc["questionId"], int):
            new_question_id = f"Q{doc['questionId']}"
            answers_collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"questionId": new_question_id}}
            )
    print("Converted existing integer questionId to string format")

    # Delete documents with question_id: null
    result = answers_collection.delete_many({"question_id": None})
    print(f"Deleted {result.deleted_count} documents with question_id: null")

    # Rename question_id to questionId if it exists in any documents
    rename_result = answers_collection.update_many(
        {"question_id": {"$exists": True}},
        {"$rename": {"question_id": "questionId"}}
    )
    print(f"Renamed question_id to questionId in {rename_result.modified_count} documents")
except Exception as e:
    print(f"Error inspecting or cleaning documents: {e}")

def store_in_db(student_data):
    try:
        # Validate input structure
        if not isinstance(student_data, dict):
            raise ValueError("student_data must be a dictionary")
        required_fields = ["roll_no", "created_at", "updated_at", "answers"]
        for field in required_fields:
            if field not in student_data:
                raise ValueError(f"Missing required field: {field}")
        if not isinstance(student_data["answers"], list):
            raise ValueError("answers must be a list")

        roll_no = student_data["roll_no"]
        created_at = datetime.fromisoformat(student_data["created_at"])
        updated_at = datetime.fromisoformat(student_data["updated_at"])
        answers = student_data["answers"]

        logging.debug(f"Full student_data: {student_data}")
        logging.debug(f"Answers array: {answers}")

        operations = []
        skipped = 0

        for i, ans in enumerate(answers):
            question_no = ans.get("question_no")
            answer_text = ans.get("answer_text")

            logging.debug(f"Answer {i}: question_no={question_no}, answer_text={answer_text}")

            # Skip if question_no is None, not an integer, or answer_text is None
            if question_no is None or not isinstance(question_no, int) or answer_text is None:
                skipped += 1
                logging.warning(f"Skipped answer {i}: question_no={question_no}, answer_text={answer_text}")
                continue

            # Map question_no (integer) to questionId (string, e.g., "Q1")
            question_id_str = f"Q{question_no}"

            # Fetch the actual question_text from the questions collection
            question_doc = questions_collection.find_one({"questionId": question_id_str})
            if not question_doc:
                logging.warning(f"No question found for questionId={question_id_str}, using default 'N/A'")
                question_text = "N/A"
            else:
                question_text = question_doc.get("question", "N/A")

            operations.append(UpdateOne(
                {"roll_no": roll_no, "questionId": question_id_str},  # Store questionId as string
                {
                    "$set": {
                        "question_text": question_text,
                        "answer_text": answer_text,
                        "updated_at": updated_at
                    },
                    "$setOnInsert": {
                        "created_at": created_at
                    }
                },
                upsert=True
            ))

        if operations:
            logging.debug(f"Executing bulk write with {len(operations)} operations")
            result = answers_collection.bulk_write(operations)
            return {
                "message": "Data stored successfully",
                "matched_count": result.matched_count,
                "modified_count": result.modified_count,
                "upserted_count": len(result.upserted_ids),
                "skipped_entries": skipped
            }
        else:
            return {
                "message": "No operations performed",
                "matched_count": 0,
                "skipped_entries": skipped
            }

    except Exception as e:
        logging.error(f"Failed to store data: {str(e)}")
        raise Exception(f"Failed to store data: {str(e)}")

def close_connection():
    client.close()
    print("MongoDB connection closed")

# Test the function
if __name__ == "__main__":
    student_data = {
        "roll_no": "211FA18115",
        "created_at": "2025-06-09T20:03:02.069Z",
        "updated_at": "2025-06-09T20:03:02.069Z",
        "answers": [
            {
                "question_no": 1,
                "question_text": None,
                "answer_text": "Machine learning (ML) is a subset of artificial intelligence (AI) that allows systems to learn from data and improve their performance on tasks over time without being explicitly programmed."
            },
            {
                "question_no": 2,
                "question_text": None,
                "answer_text": "Classification predicts discrete labels in categories (e.g., spam & not spam). Regression predicts continuous values (e.g., house price prediction)."
            },
            {
                "question_no": 3,
                "question_text": None,
                "answer_text": "Overfitting: The model learns the training data too well, but performs too bad on unseen data, leading to high variance and less bias. Underfitting: The model learns the training data to poor can't capture the patterns in both training data and testing data, leading to high bias and less variance."
            }
        ]
    }
    try:
        result = store_in_db(student_data)
        print(result)
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        close_connection()
