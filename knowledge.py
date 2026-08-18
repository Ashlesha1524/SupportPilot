"""
knowledge.py

Knowledge Base for SupportPilot.

Later this can be replaced by
FAISS + ChromaDB + Pinecone + RAG.
"""


knowledge_base = {

    "Hardware": {

        "documents":[

            "Laptop Troubleshooting Guide",

            "Hardware Maintenance SOP",

            "Device Warranty Policy"

        ],

        "faq":[

            "How to reduce laptop overheating?",

            "How to clean laptop cooling vents?",

            "How to check battery health?"

        ]

    },

    "Network":{

        "documents":[

            "VPN Configuration Guide",

            "Network Troubleshooting SOP",

            "WiFi Setup Manual"

        ],

        "faq":[

            "VPN is not connecting.",

            "Internet disconnects frequently.",

            "Unable to access company network."

        ]

    },

    "Access":{

        "documents":[

            "Password Reset SOP",

            "Account Unlock Guide",

            "MFA Configuration"

        ],

        "faq":[

            "Forgot password.",

            "Unable to login.",

            "Account locked."

        ]

    },

    "Software":{

        "documents":[

            "Application Installation Guide",

            "Software Troubleshooting SOP",

            "License Activation Manual"

        ],

        "faq":[

            "Application crashes.",

            "Unable to install software.",

            "License expired."

        ]

    }

}


def get_documents(category):

    return knowledge_base.get(

        category,

        {

            "documents":[],

            "faq":[]

        }

    )