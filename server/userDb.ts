export interface User {
  id: string;
  email: string;
  name?: string;
  profile_picture?: string;
}

const users = new Map<string, User>();

export const findUserByEmail = async (email: string): Promise<User | undefined> => {
  return Array.from(users.values()).find(user => user.email === email);
};

export const findUserById = async (id: string): Promise<User | undefined> => {
  return users.get(id);
};

export const createUser = async (user: User): Promise<User> => {
  users.set(user.id, user);
  return user;
};

export const getAllUsers = async (): Promise<User[]> => {
  return Array.from(users.values());
};
